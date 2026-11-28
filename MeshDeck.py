# -*- coding: utf-8 -*-
"""
MeshDeck - versão 1.6 (antigo Visualizador STL)
Abre modelos 3D (.stl, .3mf, .obj, .ply), mostra numa mesa de impressora e deixa
mover, girar e redimensionar a peça arrastando os controles na própria peça.

Feito em Python com PySide6 (janela) + PyOpenGL (desenho 3D) + numpy (contas).
"""
import sys
import os
import math
import re
import struct
import ctypes
import zipfile
import traceback
import xml.etree.ElementTree as ET

import numpy as np

import idiomas
from idiomas import T

# ===========================================================================
#  PARTE 1 - NÚCLEO (ler, salvar e transformar modelos). Não depende da
#  janela, então dá pra reaproveitar em outros programas (ex.: miniaturas).
# ===========================================================================

FORMATOS = (".stl", ".3mf", ".obj", ".ply")
STL_DTYPE = np.dtype([("normal", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attr", "<u2")])


def carregar_modelo(caminho):
    """Lê .stl, .3mf, .obj ou .ply e devolve um array (N, 3, 3) de triângulos."""
    ext = os.path.splitext(caminho)[1].lower()
    if ext == ".3mf":
        tris = _ler_3mf(caminho)
    elif ext == ".obj":
        tris = _ler_obj(caminho)
    elif ext == ".ply":
        tris = _ler_ply(caminho)
    else:
        tris = _ler_stl(caminho)
    if tris is None or len(tris) == 0:
        raise ValueError(T("Nenhum triângulo encontrado neste arquivo."))
    tris = np.asarray(tris, dtype=np.float32).reshape(-1, 3, 3)
    tris = tris[np.isfinite(tris).all(axis=(1, 2))]
    if len(tris) == 0:
        raise ValueError(T("O arquivo não tem triângulos válidos."))
    return np.ascontiguousarray(tris)


def _juntar(vertices, faces):
    """Transforma lista de pontos + faces (índices) em triângulos, ignorando índices ruins."""
    v = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    f = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    if len(v) == 0 or len(f) == 0:
        return None
    ok = ((f >= 0) & (f < len(v))).all(axis=1)
    return v[f[ok]]


# ---- STL ----
def _ler_stl(caminho):
    with open(caminho, "rb") as f:
        dados = f.read()
    if len(dados) < 15:
        raise ValueError(T("O arquivo está vazio ou corrompido."))
    # binário: 80 bytes de cabeçalho + 4 bytes com a quantidade + 50 bytes por triângulo
    if len(dados) >= 84:
        n = struct.unpack_from("<I", dados, 80)[0]
        if n > 0 and 84 + 50 * n == len(dados):
            return _stl_binario(dados, n)
    # texto (começa com "solid")
    if dados[:512].lstrip().lower().startswith(b"solid"):
        tris = _stl_ascii(dados)
        if tris is not None and len(tris):
            return tris
    # binário com alguns bytes a mais/a menos no fim
    if len(dados) >= 134:
        n_cab = struct.unpack_from("<I", dados, 80)[0]
        n_tam = (len(dados) - 84) // 50
        if n_cab > 0 and abs(n_cab - n_tam) <= max(2, n_tam * 0.02):
            return _stl_binario(dados, min(n_cab, n_tam))
    raise ValueError(T("Não foi possível ler este arquivo como STL."))


def _stl_binario(dados, n):
    return np.frombuffer(dados, dtype=STL_DTYPE, count=n, offset=84)["v"].astype(np.float32)


def _stl_ascii(dados):
    texto = dados.decode("latin-1", errors="ignore")
    nums = re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", texto, flags=re.IGNORECASE)
    if not nums:
        return None
    try:
        v = np.array(nums, dtype=np.float64)
    except ValueError:
        return None
    qtd = (len(v) // 3) * 3
    return v[:qtd].reshape(-1, 3, 3)


# ---- 3MF (Orca, Bambu, Prusa, Cura...) ----
def _nome_local(tag):
    return tag.rsplit("}", 1)[-1]


def _atributo(el, nome):
    for k, v in el.attrib.items():
        if _nome_local(k) == nome:
            return v
    return None


def _matriz_3mf(texto):
    m = np.identity(4)
    if texto:
        try:
            n = [float(x) for x in texto.split()]
        except ValueError:
            return m
        if len(n) == 12:
            m[:3, :3] = np.array(n[:9]).reshape(3, 3)
            m[3, :3] = n[9:12]
    return m


def _ler_3mf(caminho):
    try:
        z = zipfile.ZipFile(caminho)
    except zipfile.BadZipFile:
        raise ValueError(T("Este 3MF está corrompido (não é um arquivo compactado válido)."))
    with z:
        nomes = {n.lstrip("/").lower(): n for n in z.namelist()}
        cache = {}

        def documento(path):
            chave = path.lstrip("/").lower()
            if chave in cache:
                return cache[chave]
            if chave not in nomes:
                raise ValueError(T("O 3MF aponta para uma parte que não existe: {p}", p=path))
            raiz = ET.fromstring(z.read(nomes[chave]))
            objetos = {}
            for o in raiz.iter():
                if _nome_local(o.tag) != "object":
                    continue
                malha, comps = None, []
                for filho in o:
                    tipo = _nome_local(filho.tag)
                    if tipo == "mesh":
                        vs, ts = [], []
                        for g in filho:
                            if _nome_local(g.tag) == "vertices":
                                vs = [(float(v.get("x")), float(v.get("y")), float(v.get("z"))) for v in g]
                            elif _nome_local(g.tag) == "triangles":
                                ts = [(int(t.get("v1")), int(t.get("v2")), int(t.get("v3"))) for t in g]
                        malha = (vs, ts)
                    elif tipo == "components":
                        for c in filho:
                            comps.append((c.get("objectid"), _matriz_3mf(c.get("transform")), _atributo(c, "path")))
                objetos[o.get("id")] = (malha, comps)
            itens = [(it.get("objectid"), _matriz_3mf(it.get("transform")), _atributo(it, "path"))
                     for it in raiz.iter() if _nome_local(it.tag) == "item"]
            cache[chave] = (objetos, itens)
            return cache[chave]

        principal = "3D/3dmodel.model"
        if "_rels/.rels" in nomes:
            try:
                for r in ET.fromstring(z.read(nomes["_rels/.rels"])):
                    if r.get("Type", "").endswith("/3dmodel"):
                        principal = r.get("Target")
                        break
            except ET.ParseError:
                pass

        partes = []

        def coletar(path, oid, matriz, nivel=0):
            if nivel > 20:
                return
            objetos, _ = documento(path)
            if oid not in objetos:
                return
            malha, comps = objetos[oid]
            if malha is not None:
                t = _juntar(malha[0], malha[1])
                if t is not None and len(t):
                    pts = np.c_[t.reshape(-1, 3), np.ones(len(t) * 3)] @ matriz
                    partes.append(pts[:, :3].reshape(-1, 3, 3))
            for cid, mc, cpath in comps:
                coletar(cpath or path, cid, mc @ matriz, nivel + 1)

        objetos, itens = documento(principal)
        if itens:
            for oid, m, ipath in itens:
                coletar(ipath or principal, oid, m)
        else:
            for oid in objetos:
                coletar(principal, oid, np.identity(4))

    if not partes:
        raise ValueError(T("Nenhuma peça encontrada dentro deste 3MF."))
    return np.concatenate(partes)


# ---- OBJ ----
def _ler_obj(caminho):
    vs, faces = [], []
    with open(caminho, "r", encoding="latin-1") as f:
        for linha in f:
            p = linha.split()
            if not p:
                continue
            if p[0] == "v" and len(p) >= 4:
                vs.append((float(p[1]), float(p[2]), float(p[3])))
            elif p[0] == "f" and len(p) >= 4:
                idx = []
                for tok in p[1:]:
                    i = int(tok.split("/")[0])
                    idx.append(i - 1 if i > 0 else len(vs) + i)
                for k in range(1, len(idx) - 1):
                    faces.append((idx[0], idx[k], idx[k + 1]))
    return _juntar(vs, faces)


# ---- PLY ----
PLY_TIPOS = {"char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1", "short": "i2", "int16": "i2",
             "ushort": "u2", "uint16": "u2", "int": "i4", "int32": "i4", "uint": "u4", "uint32": "u4",
             "float": "f4", "float32": "f4", "double": "f8", "float64": "f8"}


def _ler_ply(caminho):
    with open(caminho, "rb") as f:
        dados = f.read()
    fim = dados.find(b"end_header")
    if not dados.startswith(b"ply") or fim < 0:
        raise ValueError(T("Não foi possível ler este arquivo como PLY."))
    formato, elementos = None, []
    for linha in dados[:fim].decode("latin-1").splitlines():
        p = linha.split()
        if not p:
            continue
        if p[0] == "format":
            formato = p[1]
        elif p[0] == "element":
            elementos.append((p[1], int(p[2]), []))
        elif p[0] == "property" and elementos:
            if p[1] == "list":
                elementos[-1][2].append(("list", p[2], p[3], p[4]))
            else:
                elementos[-1][2].append(("val", p[1], p[2]))
    pos = dados.find(b"\n", fim) + 1
    vertices, faces = None, []

    if formato == "ascii":
        linhas = dados[pos:].decode("latin-1").split("\n")
        i = 0
        for nome, qtd, props in elementos:
            bloco = linhas[i:i + qtd]
            i += qtd
            if nome == "vertex":
                nomes = [pp[2] for pp in props if pp[0] == "val"]
                ix = [nomes.index(c) for c in "xyz"]
                vertices = [[float(l.split()[k]) for k in ix] for l in bloco]
            elif nome == "face":
                for l in bloco:
                    n = l.split()
                    if not n:
                        continue
                    c = int(n[0])
                    idx = [int(x) for x in n[1:1 + c]]
                    for k in range(1, c - 1):
                        faces.append((idx[0], idx[k], idx[k + 1]))
    elif formato in ("binary_little_endian", "binary_big_endian"):
        fim_b = "<" if formato == "binary_little_endian" else ">"
        for nome, qtd, props in elementos:
            if all(pp[0] == "val" for pp in props):
                dt = np.dtype([(pp[2], fim_b + PLY_TIPOS[pp[1]]) for pp in props])
                arr = np.frombuffer(dados, dt, count=qtd, offset=pos)
                pos += dt.itemsize * qtd
                if nome == "vertex":
                    vertices = np.stack([arr["x"], arr["y"], arr["z"]], axis=1)
                continue
            # caminho rápido: faces só com a lista de índices e todas triângulos
            if nome == "face" and len(props) == 1:
                _, tc, ti, _ = props[0]
                dt = np.dtype([("n", fim_b + PLY_TIPOS[tc]), ("i", fim_b + PLY_TIPOS[ti], (3,))])
                if pos + dt.itemsize * qtd <= len(dados):
                    arr = np.frombuffer(dados, dt, count=qtd, offset=pos)
                    if (arr["n"] == 3).all():
                        faces = arr["i"].astype(np.int64)
                        pos += dt.itemsize * qtd
                        continue
            # caminho lento: lê face por face
            for _ in range(qtd):
                indices = None
                for pp in props:
                    if pp[0] == "list":
                        _, tc, ti, pnome = pp
                        dtc = np.dtype(fim_b + PLY_TIPOS[tc])
                        c = int(np.frombuffer(dados, dtc, 1, pos)[0])
                        pos += dtc.itemsize
                        dti = np.dtype(fim_b + PLY_TIPOS[ti])
                        vals = np.frombuffer(dados, dti, c, pos)
                        pos += dti.itemsize * c
                        if pnome in ("vertex_indices", "vertex_index"):
                            indices = vals
                    else:
                        pos += np.dtype(PLY_TIPOS[pp[1]]).itemsize
                if nome == "face" and indices is not None:
                    for k in range(1, len(indices) - 1):
                        faces.append((indices[0], indices[k], indices[k + 1]))
    else:
        raise ValueError(T("Formato de PLY desconhecido."))

    if vertices is None or len(faces) == 0:
        raise ValueError(T("Este PLY não tem faces (parece ser só uma nuvem de pontos)."))
    return _juntar(vertices, faces)


# ---- salvar e contas ----
def calcular_normais(tris):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    tam = np.linalg.norm(n, axis=1, keepdims=True)
    return (n / np.maximum(tam, 1e-12)).astype(np.float32)


def salvar_stl(caminho, tris, nome="MeshDeck"):
    """Salva os triângulos como STL binário."""
    arr = np.zeros(len(tris), dtype=STL_DTYPE)
    arr["normal"] = calcular_normais(tris)
    arr["v"] = tris
    cabecalho = nome.encode("ascii", "ignore")[:80].ljust(80, b" ")
    with open(caminho, "wb") as f:
        f.write(cabecalho)
        f.write(struct.pack("<I", len(tris)))
        f.write(arr.tobytes())


def matriz_rotacao(eixo, graus):
    t = math.radians(graus)
    c, s = math.cos(t), math.sin(t)
    if abs(graus % 90) < 1e-9:   # 90°, 180°... sem erro de arredondamento
        c, s = round(c), round(s)
    if eixo == 0:
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)
    if eixo == 1:
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


class Modelo:
    """
    Guarda o modelo original e o estado atual:
      R   = rotação (3x3)       S = escala em cada eixo da peça
      pos = centro da peça na mesa (X, Y). A peça sempre fica apoiada na mesa.
    """

    def __init__(self, tris, caminho, nome=None):
        self.caminho = caminho
        self.nome = nome or os.path.basename(caminho)
        self.original = tris
        self.versao = 0
        self.restaurar()

    def restaurar(self):
        pts = self.original.reshape(-1, 3)
        self.base = (self.original - (pts.min(0) + pts.max(0)) / 2).astype(np.float32)
        self.R = np.identity(3)
        self.S = np.ones(3)
        self.pos = np.zeros(2)
        self.recalcular()

    def recalcular(self):
        t = (self.base * self.S.astype(np.float32)) @ self.R.T.astype(np.float32)
        pts = t.reshape(-1, 3)
        mn, mx = pts.min(0).astype(np.float64), pts.max(0).astype(np.float64)
        self.desloc = np.array([(mn[0] + mx[0]) / 2 - self.pos[0], (mn[1] + mx[1]) / 2 - self.pos[1], mn[2]])
        self.atual = np.ascontiguousarray(t - self.desloc.astype(np.float32), dtype=np.float32)
        self.normais = calcular_normais(self.atual)
        self.mn, self.mx = mn - self.desloc, mx - self.desloc
        self.dim = mx - mn
        self.versao += 1

    def definir(self, R=None, S=None, pos=None):
        if R is not None:
            u, _, vt = np.linalg.svd(R)     # mantém a rotação "limpa" depois de muitas mudanças
            self.R = u @ vt
        if S is not None:
            self.S = np.maximum(np.asarray(S, dtype=np.float64), 1e-4)
        if pos is not None:
            self.pos = np.asarray(pos, dtype=np.float64).copy()
        self.recalcular()

    def girar(self, eixo, graus):
        self.definir(R=matriz_rotacao(eixo, graus) @ self.R)

    def eixo_local(self, eixo_mundo, R=None):
        """Qual eixo da peça está mais alinhado com o eixo X/Y/Z da mesa."""
        R = self.R if R is None else R
        return int(np.argmax(np.abs(R[eixo_mundo, :])))

    def escala_mundo(self):
        """Escala (%) vista nos eixos X, Y, Z da mesa."""
        return np.array([self.S[self.eixo_local(w)] for w in range(3)])

    @property
    def uniforme(self):
        return bool(np.allclose(self.S, self.S[0], rtol=1e-6))

    def previa(self, R2, S2, pos2):
        """
        Calcula rápido como a peça ficaria com outro R/S/pos, sem refazer a malha.
        Devolve a matriz 4x4 para desenhar e a caixa (mn, mx) resultante.
        """
        S2 = np.maximum(np.asarray(S2, dtype=np.float64), 1e-4)
        M = self.R @ np.diag(S2 / self.S) @ np.asarray(R2).T
        q0 = self.desloc @ M
        if np.allclose(M, np.identity(3)):
            mn, mx = self.mn + self.desloc, self.mx + self.desloc
        else:
            q = self.atual.reshape(-1, 3) @ M.astype(np.float32)
            mn, mx = q.min(0) + q0, q.max(0) + q0
        d2 = np.array([(mn[0] + mx[0]) / 2 - pos2[0], (mn[1] + mx[1]) / 2 - pos2[1], mn[2]])
        G = np.identity(4)
        G[:3, :3] = M.T
        G[:3, 3] = q0 - d2
        return {"G": G, "mn": mn - d2, "mx": mx - d2, "dim": mx - mn}


def raio_toca_triangulos(origem, direcao, tris):
    """Distância até o primeiro triângulo atingido por um raio (ou None)."""
    o = origem.astype(np.float32)
    d = direcao.astype(np.float32)
    v0 = tris[:, 0]
    e1 = tris[:, 1] - v0
    e2 = tris[:, 2] - v0
    p = np.cross(d, e2)
    det = (e1 * p).sum(1)
    ok = np.abs(det) > 1e-12
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    tv = o - v0
    u = (tv * p).sum(1) * inv
    q = np.cross(tv, e1)
    v = (q * d).sum(1) * inv
    t = (e2 * q).sum(1) * inv
    acerto = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
    return float(t[acerto].min()) if acerto.any() else None


# ---- várias peças + desfazer/refazer ----
class Cena:
    """As peças que estão na mesa, qual está selecionada e o histórico (Ctrl+Z / Ctrl+Y)."""
    LIMITE_HISTORICO = 60

    def __init__(self):
        self.pecas = []
        self.selecionada = None
        self._desfazer = []
        self._refazer = []

    def estado(self):
        return ([(m, m.R.copy(), m.S.copy(), m.pos.copy()) for m in self.pecas], self.selecionada)

    def registrar(self):
        """Chamar ANTES de qualquer mudança, para poder desfazer depois."""
        self._desfazer.append(self.estado())
        if len(self._desfazer) > self.LIMITE_HISTORICO:
            self._desfazer.pop(0)
        self._refazer.clear()

    def _aplicar(self, est):
        lista, sel = est
        self.pecas = [item[0] for item in lista]
        for m, R, S, pos in lista:
            if not (np.array_equal(m.R, R) and np.array_equal(m.S, S) and np.array_equal(m.pos, pos)):
                m.R, m.S, m.pos = R.copy(), S.copy(), pos.copy()
                m.recalcular()
        self.selecionada = sel if any(sel is m for m in self.pecas) else (self.pecas[0] if self.pecas else None)

    def desfazer(self):
        if not self._desfazer:
            return False
        self._refazer.append(self.estado())
        self._aplicar(self._desfazer.pop())
        return True

    def refazer(self):
        if not self._refazer:
            return False
        self._desfazer.append(self.estado())
        self._aplicar(self._refazer.pop())
        return True

    def limites(self):
        if not self.pecas:
            return None, None
        mn = np.min([m.mn for m in self.pecas], axis=0)
        mx = np.max([m.mx for m in self.pecas], axis=0)
        return mn, mx

    def adicionar(self, modelo, folga=5.0):
        """Coloca a peça nova à direita das que já estão na mesa."""
        if self.pecas:
            _, mx = self.limites()
            modelo.definir(pos=np.array([mx[0] + folga + modelo.dim[0] / 2, 0.0]))
        self.pecas.append(modelo)
        self.selecionada = modelo

    def remover(self, modelo):
        self.pecas = [m for m in self.pecas if m is not modelo]
        if self.selecionada is modelo:
            self.selecionada = self.pecas[-1] if self.pecas else None

    def organizar(self, largura, folga=5.0):
        """Espalha as peças em fileiras, sem encostar uma na outra, centralizadas na mesa."""
        if not self.pecas:
            return
        itens = sorted(self.pecas, key=lambda m: -m.dim[1])
        x = y = altura_linha = 0.0
        lugares = []
        for m in itens:
            w, d = m.dim[0], m.dim[1]
            if x > 0 and x + w > largura:
                x = 0.0
                y += altura_linha + folga
                altura_linha = 0.0
            lugares.append((m, np.array([x + w / 2, y + d / 2]), w, d))
            x += w + folga
            altura_linha = max(altura_linha, d)
        mn = np.min([p - [w / 2, d / 2] for _, p, w, d in lugares], axis=0)
        mx = np.max([p + [w / 2, d / 2] for _, p, w, d in lugares], axis=0)
        centro = (mn + mx) / 2
        for m, p, _, _ in lugares:
            m.definir(pos=p - centro)


# ---- arquivos .zip ----
LIMITE_ZIP = 1024 * 1024 * 1024  # 1 GB por peça


def pasta_temporaria(sub):
    import tempfile
    p = os.path.join(tempfile.gettempdir(), "VisualizadorSTL", sub)
    os.makedirs(p, exist_ok=True)
    return p


def modelos_no_zip(caminho):
    with zipfile.ZipFile(caminho) as z:
        return [i.filename for i in z.infolist()
                if not i.is_dir() and i.filename.lower().endswith(FORMATOS)
                and "__macosx" not in i.filename.lower() and i.file_size <= LIMITE_ZIP]


def extrair_do_zip(caminho, membros, destino):
    """Copia as peças escolhidas do zip para uma pasta temporária, com nomes seguros."""
    saida = []
    with zipfile.ZipFile(caminho) as z:
        for i, membro in enumerate(membros):
            base = re.sub(r"[^\w.\- ]", "_", os.path.basename(membro)) or f"peca{i}.stl"
            alvo = os.path.join(destino, f"{i:03d}_{base}")
            with open(alvo, "wb") as f:
                f.write(z.read(membro))
            saida.append((membro, alvo))
    return saida


def carregar_para_miniatura(caminho):
    """Lê o modelo (ou o primeiro modelo de dentro de um .zip)."""
    if caminho.lower().endswith(".zip"):
        membros = modelos_no_zip(caminho)
        if not membros:
            raise ValueError("zip sem modelos")
        import tempfile
        fd, temp = tempfile.mkstemp(suffix=os.path.splitext(membros[0])[1], dir=pasta_temporaria("miniaturas"))
        os.close(fd)
        try:
            with zipfile.ZipFile(caminho) as z, open(temp, "wb") as f:
                f.write(z.read(membros[0]))
            return carregar_modelo(temp)
        finally:
            try:
                os.remove(temp)
            except OSError:
                pass
    return carregar_modelo(caminho)


# ---- miniaturas (desenhadas só com numpy, sem placa de vídeo) ----
def miniatura(tris, tam=160, cor=(0.31, 0.76, 0.97), yaw=-55.0, pitch=28.0):
    """Desenha o modelo em vista isométrica e devolve uma imagem RGBA (tam x tam) em uint8."""
    t = np.asarray(tris, dtype=np.float32).reshape(-1, 3, 3)
    rng = np.random.default_rng(0)
    if len(t) > 600000:
        t = t[rng.choice(len(t), 600000, replace=False)]
    y, p = math.radians(yaw), math.radians(pitch)
    d = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
    s = np.cross(-d, [0.0, 0.0, 1.0])
    s /= np.linalg.norm(s)
    u = np.cross(s, -d)
    B = np.stack([s, u, d]).astype(np.float32)
    q = t @ B.T
    pts = q.reshape(-1, 3)
    mn, mx = pts.min(0), pts.max(0)
    S = tam * 2   # desenha no dobro e reduz (bordas suaves)
    esc = S * 0.86 / max(float(mx[0] - mn[0]), float(mx[1] - mn[1]), 1e-9)
    cx, cy = (mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2
    X = (q[..., 0] - cx) * esc + S / 2
    Y = S / 2 - (q[..., 1] - cy) * esc
    Z = q[..., 2]

    n = calcular_normais(t) @ B.T
    n[n[:, 2] < 0] *= -1
    l1 = np.array([-0.4, 0.6, 1.0], dtype=np.float32)
    l1 /= np.linalg.norm(l1)
    l2 = np.array([0.6, -0.4, 0.5], dtype=np.float32)
    l2 /= np.linalg.norm(l2)
    luz = np.clip(0.24 + 0.72 * np.maximum(n @ l1, 0) + 0.28 * np.maximum(n @ l2, 0), 0, 1.15)

    e1x, e1y = X[:, 1] - X[:, 0], Y[:, 1] - Y[:, 0]
    e2x, e2y = X[:, 2] - X[:, 0], Y[:, 2] - Y[:, 0]
    area = 0.5 * np.abs(e1x * e2y - e1y * e2x)
    k = np.clip(np.ceil(area * 4.0), 1, 20000).astype(np.int64)
    total = int(k.sum())
    if total > 6_000_000:
        k = np.maximum(1, (k * (6_000_000 / total)).astype(np.int64))
    idx = np.repeat(np.arange(len(t)), k)
    r1 = rng.random(len(idx), dtype=np.float32)
    r2 = rng.random(len(idx), dtype=np.float32)
    fora = r1 + r2 > 1
    r1[fora], r2[fora] = 1 - r1[fora], 1 - r2[fora]

    def ponto(A):
        a = A[idx]
        return a[:, 0] + r1 * (a[:, 1] - a[:, 0]) + r2 * (a[:, 2] - a[:, 0])

    px = np.concatenate([ponto(X), X.ravel()])
    py = np.concatenate([ponto(Y), Y.ravel()])
    pz = np.concatenate([ponto(Z), Z.ravel()])
    pl = np.concatenate([luz[idx], np.repeat(luz, 3)])
    ix, iy = px.astype(np.int64), py.astype(np.int64)
    ok = (ix >= 0) & (ix < S) & (iy >= 0) & (iy < S)
    pix, pz, pl = iy[ok] * S + ix[ok], pz[ok], pl[ok]
    ordem = np.lexsort((-pz, pix))           # por pixel, o mais perto primeiro
    ps = pix[ordem]
    primeiro = np.r_[True, ps[1:] != ps[:-1]]
    vis = ordem[primeiro]

    img = np.zeros((S * S, 4), dtype=np.float32)
    img[pix[vis], :3] = np.clip(np.asarray(cor, dtype=np.float32)[None, :] * pl[vis, None], 0, 1)
    img[pix[vis], 3] = 1.0
    img = img.reshape(S, S, 4)

    # tapa furinhos de 1 pixel
    a = img[..., 3]
    pad = np.pad(img, ((1, 1), (1, 1), (0, 0)))
    viz = sum(pad[1 + dy:S + 1 + dy, 1 + dx:S + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
              if dy or dx)
    furo = (a == 0) & (viz[..., 3] >= 5)
    img[furo, :3] = viz[furo, :3] / viz[furo, 3:4]
    img[furo, 3] = 1.0

    # reduz pela metade (média de 2x2)
    img = img.reshape(tam, 2, tam, 2, 4)
    alfa = img[..., 3].mean(axis=(1, 3))
    rgb = (img[..., :3] * img[..., 3:4]).sum(axis=(1, 3)) / np.maximum(img[..., 3].sum(axis=(1, 3)), 1e-6)[..., None]
    out = np.dstack([rgb, alfa])
    return np.ascontiguousarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


# ===========================================================================
#  PARTE 2 - JANELA
# ===========================================================================

import json
import time
import shutil
import hashlib
import subprocess

import OpenGL
OpenGL.ERROR_CHECKING = False
from OpenGL import GL as gl

from PySide6.QtCore import (Qt, QSettings, QTimer, Signal, QObject, QRunnable, QThreadPool, QSize, QLocale,
                            QProcess, QRectF, QEvent)
from PySide6.QtGui import (QSurfaceFormat, QColor, QIcon, QAction, QKeySequence, QPalette, QImage,
                           QPixmap, QPainter, QFont, QCursor, QPen)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QToolButton, QDoubleSpinBox,
    QCheckBox, QComboBox, QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, QScrollArea,
    QFileDialog, QMessageBox, QColorDialog, QFrame, QTabWidget, QListWidget, QListWidgetItem,
    QListView, QAbstractItemView, QLineEdit, QMenu, QDialog, QDialogButtonBox, QStackedWidget,
    QButtonGroup, QSizePolicy, QSlider,
)

AUTOR = "DarkDragonal"
LINK_GITHUB = "https://github.com/DarkDragonal/meshdeck"
LINK_KOFI = "https://ko-fi.com/darkdragonal"
APP_NOME = "MeshDeck"   # nome do programa (não se traduz)
# as pastas de dados e as configurações continuam com o nome antigo "VisualizadorSTL"
# para quem atualizar não perder o cache de miniaturas nem as preferências
VERSAO = "1.7"
COR_DESTAQUE = "#00ae9b"
CORES_EIXOS = ((0.95, 0.32, 0.32), (0.36, 0.86, 0.36), (0.38, 0.58, 1.0))
COR_HOVER = (1.0, 0.85, 0.2)
TAM_MINIATURA = 256

# ---- encaixes para outros programas ----
# Um programa que use o MeshDeck por dentro pode acrescentar opções aos menus do botão direito
# sem alterar este arquivo, pondo funções nestas listas:
#   EXTRAS_MENU_MESA:     funcao(janela, menu)    -> menu da mesa (visualizador)
#   EXTRAS_MENU_ARQUIVOS: funcao(menu, caminhos)  -> menu dos modelos da biblioteca
# Cada função adiciona as ações dela no menu (menu.addAction(texto, callback)).
EXTRAS_MENU_MESA = []
EXTRAS_MENU_ARQUIVOS = []


def _aplicar_extras(lista, *args):
    for funcao in list(lista):
        try:
            funcao(*args)
        except Exception as ex:   # um encaixe com problema não pode derrubar o menu
            _registrar_erro(f"encaixe de menu {getattr(funcao, '__name__', funcao)}: {ex!r}")


# ---- fatiador (para quem imprime em 3D) ----
# Fatiadores conhecidos e onde costumam ser instalados no Windows ("*" = qualquer versão).
FATIADORES = [
    ("OrcaSlicer", [r"{PF}\OrcaSlicer\orca-slicer.exe", r"{PF}\OrcaSlicer\OrcaSlicer.exe",
                    r"{LAD}\Programs\OrcaSlicer\orca-slicer.exe"]),
    ("PrusaSlicer", [r"{PF}\Prusa3D\PrusaSlicer\prusa-slicer.exe", r"{PF}\PrusaSlicer\prusa-slicer.exe"]),
    ("Bambu Studio", [r"{PF}\Bambu Studio\bambu-studio.exe"]),
    ("UltiMaker Cura", [r"{PF}\UltiMaker Cura*\UltiMaker-Cura.exe", r"{PF}\Ultimaker Cura*\Ultimaker-Cura.exe",
                        r"{PF}\Ultimaker Cura*\Cura.exe"]),
    ("SuperSlicer", [r"{PF}\SuperSlicer\superslicer.exe", r"{PF}\SuperSlicer*\superslicer.exe"]),
    ("Creality Print", [r"{PF}\Creality\Creality Print*\CrealityPrint.exe"]),
    ("CHITUBOX", [r"{PF}\CHITUBOX\CHITUBOX.exe", r"{PF}\CHITUBOX*\CHITUBOX*.exe", r"{PF}\CHITUBOX_Basic\CHITUBOX*.exe"]),
    ("Lychee Slicer", [r"{LAD}\Programs\lychee-slicer\Lychee Slicer.exe", r"{PF}\Mango3D\Lychee*\Lychee*.exe",
                       r"{PF}\Lychee Slicer\Lychee Slicer.exe"]),
]
FATIADORES_NOMES = [n for n, _ in FATIADORES]
FORMATOS_FATIADOR = (".stl", ".3mf", ".obj", ".ply")


def procurar_fatiador(nome):
    """Procura o executável de um fatiador conhecido nas pastas de instalação comuns."""
    import glob
    lugares = {"PF": [os.environ.get("ProgramFiles", r"C:\Program Files"),
                      os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")],
               "LAD": [os.environ.get("LOCALAPPDATA", "")]}
    for n, padroes in FATIADORES:
        if n != nome:
            continue
        for padrao in padroes:
            chave = "PF" if padrao.startswith("{PF}") else "LAD"
            for base in lugares[chave]:
                if base:
                    achados = sorted(glob.glob(padrao.replace("{" + chave + "}", base)), reverse=True)
                    if achados:
                        return achados[0]
    return None


def fatiadores_instalados():
    return [n for n in FATIADORES_NOMES if procurar_fatiador(n)]


def ler_fatiador():
    """(nome, executável escolhido ou "")."""
    c = QSettings("VisualizadorSTL", "VisualizadorSTL")
    nome = str(c.value("fatiador_nome", "") or "")
    if not nome:
        instalados = fatiadores_instalados()
        nome = instalados[0] if instalados else "OrcaSlicer"
    return nome, str(c.value("fatiador_exe", "") or "")


def gravar_fatiador(nome, exe=""):
    c = QSettings("VisualizadorSTL", "VisualizadorSTL")
    c.setValue("fatiador_nome", nome)
    c.setValue("fatiador_exe", exe)
    c.sync()


def exe_fatiador():
    """(nome, executável ou None) do fatiador escolhido em Configurações."""
    nome, exe = ler_fatiador()
    if exe and os.path.isfile(exe):
        return nome, exe
    return nome, procurar_fatiador(nome)


def localizar_fatiador(parent):
    """Pede o executável do fatiador (quando ele não está numa pasta conhecida)."""
    arq, _ = QFileDialog.getOpenFileName(parent, T("Onde está o fatiador?"),
                                         os.environ.get("ProgramFiles", ""), T("Programas") + " (*.exe)")
    if not arq:
        return None
    base = os.path.splitext(os.path.basename(arq))[0].lower()
    nome = next((n for n in FATIADORES_NOMES if n.split()[0].lower() in base), os.path.splitext(os.path.basename(arq))[0])
    gravar_fatiador(nome, arq)
    return nome, arq


def _exe_fatiador_ou_perguntar(parent):
    nome, exe = exe_fatiador()
    if exe is None:
        QMessageBox.information(parent, nome_app(), T("{f} não foi encontrado neste computador. Indique onde está o "
                                                      "programa.", f=nome))
        r = localizar_fatiador(parent)
        if r is None:
            return nome, None
        nome, exe = r
    return nome, exe


def abrir_no_fatiador(parent, caminhos):
    """Abre os arquivos no fatiador escolhido em Configurações."""
    nome, exe = _exe_fatiador_ou_perguntar(parent)
    if exe is None:
        return False
    try:
        subprocess.Popen([exe, *caminhos])
    except Exception as ex:
        QMessageBox.warning(parent, nome_app(), T("Não foi possível abrir no {f}: {e}", f=nome, e=ex))
        return False
    return True


def salvar_3mf(caminho, pecas):
    """pecas = lista de (nome, triângulos). Junta vértices repetidos para o fatiador ver a malha fechada."""
    from xml.sax.saxutils import quoteattr
    objetos, itens = [], []
    for i, (nome, tris) in enumerate(pecas, start=1):
        v = np.asarray(tris, dtype=np.float32).reshape(-1, 3)
        unicos, inv = np.unique(v, axis=0, return_inverse=True)
        faces = inv.reshape(-1, 3)
        faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
        vtxt = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in unicos.tolist())
        ttxt = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces.tolist())
        objetos.append(f'<object id="{i}" name={quoteattr(nome)} type="model"><mesh><vertices>{vtxt}</vertices>'
                       f'<triangles>{ttxt}</triangles></mesh></object>')
        itens.append(f'<item objectid="{i}"/>')
    modelo = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<model unit="millimeter" xml:lang="en-US" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
              f'<resources>{"".join(objetos)}</resources><build>{"".join(itens)}</build></model>')
    tipos = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
             '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", modelo)


EXTENSOES_ABRIR = FORMATOS + (".zip",)


def nome_app():
    return APP_NOME


def filtro_arquivos():
    t = T("Modelos 3D")
    return (f"{t} (*.stl *.3mf *.obj *.ply *.zip);;STL (*.stl);;3MF (*.3mf);;OBJ (*.obj);;PLY (*.ply);;"
            f"ZIP (*.zip);;{T('Todos os arquivos')} (*.*)")


def data_hora(ts):
    return time.strftime(idiomas.FORMATO_DATA.get(idiomas.atual(), "%d/%m/%Y %H:%M"), time.localtime(ts))


def caminho_recurso(nome):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome)


def pasta_dados(sub=None):
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    p = os.path.join(base, "VisualizadorSTL", sub) if sub else os.path.join(base, "VisualizadorSTL")
    os.makedirs(p, exist_ok=True)
    return p


def num(v, casas=1):
    """Formata número no jeito do idioma escolhido (1.234,5 / 1,234.5 ...)."""
    dec, mil = idiomas.SEPARADORES.get(idiomas.atual(), (",", "."))
    s = f"{v:,.{casas}f}"
    return s.replace(",", "\x00").replace(".", dec).replace("\x00", mil)


def _normalizar(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def matriz_perspectiva(fov_graus, aspecto, perto, longe):
    f = 1.0 / math.tan(math.radians(fov_graus) / 2)
    return np.array([
        [f / aspecto, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (longe + perto) / (perto - longe), 2 * longe * perto / (perto - longe)],
        [0, 0, -1, 0],
    ], dtype=np.float64)


def matriz_olhar(olho, alvo, cima):
    f = _normalizar(alvo - olho)
    s = _normalizar(np.cross(f, cima))
    u = np.cross(s, f)
    m = np.identity(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[0, 3], m[1, 3], m[2, 3] = -np.dot(s, olho), -np.dot(u, olho), np.dot(f, olho)
    return m


def _dist_ponto_segmento(p, a, b):
    ab = b - a
    t = 0.0 if np.dot(ab, ab) < 1e-9 else max(0.0, min(1.0, np.dot(p - a, ab) / np.dot(ab, ab)))
    return float(np.linalg.norm(p - (a + ab * t)))


# ---------------------------------------------------------------------------
#  Área 3D
# ---------------------------------------------------------------------------
class Visor(QOpenGLWidget):
    FOV = 35.0
    VISTAS = {"iso": (-55.0, 28.0), "frente": (-90.0, 0.0), "topo": (-90.0, 89.0),
              "lado": (0.0, 0.0), "tras": (90.0, 0.0)}
    PONTA = 0.24   # tamanho da ponta da seta (fração do comprimento)

    alterado = Signal()            # uma peça mudou (fim de um arrasto)
    previa_mudou = Signal(object)  # medidas durante o arrasto
    selecao_mudou = Signal()
    menu_pedido = Signal(object)   # posição global do clique direito

    def __init__(self, cena, parent=None):
        super().__init__(parent)
        self.cena = cena
        self.cor = QColor("#4fc3f7")
        self.modo = 0  # 0 = sólido, 1 = malha, 2 = sólido com malha
        self.mostrar_mesa = True
        self.mesa = [225.0, 225.0, 265.0]
        self.manter_proporcao = True
        self.ferramenta = None   # None, "mover", "girar", "escala", "medir"
        self.yaw, self.pitch = self.VISTAS["iso"]
        self.dist = 450.0
        self.alvo = np.zeros(3)
        self._gpu = {}
        self._ultimo = None
        self._botao = None
        self._hover = None
        self._arr = None      # arrasto de controle em andamento
        self._prev = None     # prévia da peça selecionada durante o arrasto
        self._novo = None
        self._medidas = []
        self._sem_controles = False
        self._moveu = False
        self._inicio_clique = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)
        self._montar_sobreposicoes()
        self.enquadrar()

    @property
    def sel(self):
        return self.cena.selecionada

    # ---- botões por cima do 3D ----
    NOMES_FERRAMENTAS = {"mover": "Mover", "girar": "Rotacionar", "escala": "Escalar", "medir": "Medir distância"}

    def _montar_sobreposicoes(self):
        self.dica = QLabel(T("Arraste um modelo 3D para cá\n(.stl  .3mf  .obj  .ply  .zip)\nou use  “Abrir…”"), self)
        self.dica.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dica.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.dica.setStyleSheet("color: rgba(255,255,255,150); font-size: 18px; background: transparent;")

        self.pilula = QLabel(self)
        self.pilula.setObjectName("pilula")
        self.pilula.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.pilula.hide()

        self.barra_vistas = QFrame(self)
        self.barra_vistas.setObjectName("barra3d")
        lay = QHBoxLayout(self.barra_vistas)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        for texto, nome, dica in (("Iso", "iso", "Vista isométrica"), ("Frente", "frente", "Vista frontal"),
                                  ("Topo", "topo", "Vista superior"), ("Lado", "lado", "Vista lateral"),
                                  ("Trás", "tras", "Vista traseira")):
            b = QToolButton()
            b.setText(T(texto))
            b.setToolTip(T(dica))
            b.clicked.connect(lambda _=False, n=nome: self.vista(n))
            lay.addWidget(b)
        b = QToolButton()
        b.setText("⛶")
        b.setToolTip(T("Ajustar à tela (F ou duplo clique)"))
        b.clicked.connect(self.enquadrar)
        lay.addWidget(b)

        self.lb_arrasto = QLabel(self)
        self.lb_arrasto.setObjectName("bolha")
        self.lb_arrasto.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lb_arrasto.hide()

        self.lb_medida = QLabel(self)
        self.lb_medida.setObjectName("bolha")
        self.lb_medida.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lb_medida.hide()
        self._atualizar_barras()

    def _atualizar_barras(self):
        if self.ferramenta:
            self.pilula.setText(T("{ferramenta}   ·   Esc para sair", ferramenta=T(self.NOMES_FERRAMENTAS[self.ferramenta])))
            self.pilula.adjustSize()
            self.pilula.move(12, 12)
            self.pilula.show()
        else:
            self.pilula.hide()

    def _posicionar_medida(self):
        self.lb_medida.adjustSize()
        self.lb_medida.move((self.width() - self.lb_medida.width()) // 2,
                            self.height() - self.lb_medida.height() - 14)

    def _atualizar_medida(self):
        if self.ferramenta != "medir":
            self.lb_medida.hide()
            return
        if len(self._medidas) == 2:
            a, b = self._medidas
            d = b - a
            self.lb_medida.setText(T("Distância: {d} mm     ΔX {x}  ·  ΔY {y}  ·  ΔZ {z} mm",
                                     d=num(float(np.linalg.norm(d)), 2), x=num(abs(d[0]), 2),
                                     y=num(abs(d[1]), 2), z=num(abs(d[2]), 2)))
        elif len(self._medidas) == 1:
            self.lb_medida.setText(T("Selecione o segundo ponto"))
        else:
            self.lb_medida.setText(T("Selecione o primeiro ponto no objeto"))
        self._posicionar_medida()
        self.lb_medida.show()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.dica.setGeometry(self.rect())
        self.barra_vistas.adjustSize()
        self.barra_vistas.move(self.width() - self.barra_vistas.width() - 12, 12)
        self._posicionar_medida()

    def definir_ferramenta(self, k):
        if k in ("mover", "girar", "escala") and self.sel is None:
            k = None
        if not self.cena.pecas:
            k = None
        if k != "medir":
            self._medidas = []
        self.ferramenta = k
        self._hover = None
        self._atualizar_barras()
        self._atualizar_medida()
        self.unsetCursor()
        self.update()

    def atualizar(self, enquadrar=False, manter_medidas=False):
        """Chamar depois de qualquer mudança nas peças."""
        self._prev = self._novo = self._arr = None
        self.dica.setVisible(not self.cena.pecas)
        if not manter_medidas:
            self._medidas = []
        if (self.ferramenta in ("mover", "girar", "escala") and self.sel is None) or not self.cena.pecas:
            self.ferramenta = None
        self._atualizar_barras()
        self._atualizar_medida()
        if enquadrar:
            self.enquadrar()
        self.update()

    def _caixa(self, m=None):
        m = self.sel if m is None else m
        if m is self.sel and self._prev is not None:
            return self._prev["mn"], self._prev["mx"]
        return m.mn, m.mx

    def fora_da_mesa(self, mn, mx):
        w, d, h = self.mesa
        tol = 0.01
        return bool(mn[0] < -w / 2 - tol or mx[0] > w / 2 + tol or mn[1] < -d / 2 - tol
                    or mx[1] > d / 2 + tol or mx[2] > h + tol)

    def capturar(self):
        """Imagem do 3D sem os controles (para salvar em PNG)."""
        self._sem_controles = True
        try:
            img = self.grabFramebuffer()
        finally:
            self._sem_controles = False
            self.update()
        return img

    # ---- câmera ----
    def _olho(self):
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        return self.alvo + self.dist * np.array([math.cos(p) * math.cos(y),
                                                 math.cos(p) * math.sin(y),
                                                 math.sin(p)])

    def _matrizes(self):
        aspecto = max(self.width(), 1) / max(self.height(), 1)
        perto = max(self.dist * 0.01, 0.05)
        longe = self.dist * 20 + max(self.mesa) * 4
        proj = matriz_perspectiva(self.FOV, aspecto, perto, longe)
        vis = matriz_olhar(self._olho(), self.alvo, np.array([0.0, 0.0, 1.0]))
        return proj, vis

    def _mvp(self):
        proj, vis = self._matrizes()
        return proj @ vis

    def _tela(self, p, mvp):
        c = mvp @ np.append(p, 1.0)
        if c[3] <= 1e-9:
            return None
        n = c[:3] / c[3]
        return np.array([(n[0] + 1) / 2 * self.width(), (1 - n[1]) / 2 * self.height()])

    def _raio_mouse(self, m, mvp):
        inv = np.linalg.inv(mvp)
        x = 2 * m[0] / max(self.width(), 1) - 1
        y = 1 - 2 * m[1] / max(self.height(), 1)
        a = inv @ np.array([x, y, -1.0, 1.0])
        b = inv @ np.array([x, y, 1.0, 1.0])
        a, b = a[:3] / a[3], b[:3] / b[3]
        return a, _normalizar(b - a)

    def _ponto_no_plano(self, m, mvp, z):
        o, d = self._raio_mouse(m, mvp)
        if abs(d[2]) < 1e-6:
            return None
        t = (z - o[2]) / d[2]
        return None if t <= 0 else o + d * t

    def _tocar(self, m):
        """Qual peça está embaixo do mouse, e em que ponto."""
        o, d = self._raio_mouse(m, self._mvp())
        melhor = None
        for peca in self.cena.pecas:
            t = raio_toca_triangulos(o, d, peca.atual)
            if t is not None and (melhor is None or t < melhor[0]):
                melhor = (t, peca)
        if melhor is None:
            return None
        return melhor[1], o + d * melhor[0]

    def enquadrar(self):
        mn, mx = self.cena.limites()
        if mn is not None:
            self.alvo = (mn + mx) / 2
            raio = max(float(np.linalg.norm(mx - mn)) / 2, 1.0)
        else:
            self.alvo = np.zeros(3)
            raio = float(np.linalg.norm(self.mesa[:2])) / 2
        aspecto = max(self.width(), 1) / max(self.height(), 1)
        dist = raio / math.sin(math.radians(self.FOV / 2)) * 1.15
        if aspecto < 1:
            dist /= aspecto
        self.dist = dist
        self.update()

    def vista(self, nome):
        self.yaw, self.pitch = self.VISTAS[nome]
        self.enquadrar()

    # ---- OpenGL ----
    def initializeGL(self):
        self._gpu = {}                # contexto novo: buffers antigos não valem mais
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_MULTISAMPLE)
        gl.glEnable(gl.GL_NORMALIZE)
        gl.glShadeModel(gl.GL_SMOOTH)
        gl.glEnable(gl.GL_LIGHT0)
        gl.glEnable(gl.GL_LIGHT1)
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_DIFFUSE, (0.75, 0.75, 0.75, 1.0))
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_SPECULAR, (0.35, 0.35, 0.35, 1.0))
        gl.glLightfv(gl.GL_LIGHT1, gl.GL_DIFFUSE, (0.30, 0.30, 0.32, 1.0))
        gl.glLightfv(gl.GL_LIGHT1, gl.GL_SPECULAR, (0.0, 0.0, 0.0, 1.0))
        gl.glLightModelfv(gl.GL_LIGHT_MODEL_AMBIENT, (0.22, 0.22, 0.24, 1.0))
        gl.glLightModeli(gl.GL_LIGHT_MODEL_TWO_SIDE, gl.GL_TRUE)
        gl.glEnable(gl.GL_COLOR_MATERIAL)
        gl.glColorMaterial(gl.GL_FRONT_AND_BACK, gl.GL_AMBIENT_AND_DIFFUSE)
        gl.glMaterialfv(gl.GL_FRONT_AND_BACK, gl.GL_SPECULAR, (0.4, 0.4, 0.4, 1.0))
        gl.glMaterialf(gl.GL_FRONT_AND_BACK, gl.GL_SHININESS, 40.0)
        gl.glEnable(gl.GL_LINE_SMOOTH)

    def _sincronizar_gpu(self):
        """Manda para a placa de vídeo as peças novas ou alteradas, e apaga as que saíram."""
        vivas = {id(m): m for m in self.cena.pecas}
        for chave in list(self._gpu):
            e = self._gpu[chave]
            if chave not in vivas or vivas[chave] is not e[0]:
                try:
                    gl.glDeleteBuffers(2, e[2])
                except Exception:
                    pass
                del self._gpu[chave]
        for m in self.cena.pecas:
            e = self._gpu.get(id(m))
            if e is not None and e[1] == m.versao:
                continue
            if e is not None:
                try:
                    gl.glDeleteBuffers(2, e[2])
                except Exception:
                    pass
            v = np.ascontiguousarray(m.atual.reshape(-1, 3), dtype=np.float32)
            n = np.ascontiguousarray(np.repeat(m.normais, 3, axis=0), dtype=np.float32)
            vbo = gl.glGenBuffers(2)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo[0])
            gl.glBufferData(gl.GL_ARRAY_BUFFER, v.nbytes, v, gl.GL_STATIC_DRAW)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo[1])
            gl.glBufferData(gl.GL_ARRAY_BUFFER, n.nbytes, n, gl.GL_STATIC_DRAW)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            self._gpu[id(m)] = [m, m.versao, vbo, len(v)]

    def paintGL(self):
        self._sincronizar_gpu()
        gl.glClearColor(0.12, 0.13, 0.15, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        self._desenhar_fundo()

        proj, vis = self._matrizes()
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadMatrixf(np.ascontiguousarray(proj.T, dtype=np.float32))
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        # luzes presas na câmera (sempre iluminando de frente)
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_POSITION, (-0.4, 0.6, 1.0, 0.0))
        gl.glLightfv(gl.GL_LIGHT1, gl.GL_POSITION, (0.6, -0.4, 0.5, 0.0))
        gl.glLoadMatrixf(np.ascontiguousarray(vis.T, dtype=np.float32))

        if self.mostrar_mesa:
            self._desenhar_mesa()
        for m in self.cena.pecas:
            self._desenhar_peca(m)
        if not self._sem_controles:
            self._desenhar_selecao()
            self._desenhar_medidas()
            self._desenhar_controles()

    def _desenhar_fundo(self):
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_LIGHTING)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        gl.glBegin(gl.GL_QUADS)
        gl.glColor3f(0.20, 0.22, 0.25)
        gl.glVertex2f(-1, 1)
        gl.glVertex2f(1, 1)
        gl.glColor3f(0.09, 0.10, 0.11)
        gl.glVertex2f(1, -1)
        gl.glVertex2f(-1, -1)
        gl.glEnd()
        gl.glEnable(gl.GL_DEPTH_TEST)

    def _desenhar_mesa(self):
        w, d = self.mesa[0], self.mesa[1]
        x0, x1, y0, y1 = -w / 2, w / 2, -d / 2, d / 2
        gl.glDisable(gl.GL_LIGHTING)

        # placa (só aparece vista de cima)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glColor3f(0.17, 0.18, 0.20)
        gl.glBegin(gl.GL_QUADS)
        gl.glVertex3f(x0, y0, -0.3)
        gl.glVertex3f(x1, y0, -0.3)
        gl.glVertex3f(x1, y1, -0.3)
        gl.glVertex3f(x0, y1, -0.3)
        gl.glEnd()
        gl.glDisable(gl.GL_CULL_FACE)

        # grade de 10 em 10 mm (mais clara a cada 50 mm), partindo do centro
        gl.glLineWidth(1.0)
        gl.glBegin(gl.GL_LINES)
        z = -0.15
        for eixo_x in (True, False):
            limite = w / 2 if eixo_x else d / 2
            k = 0
            while k * 10 <= limite + 1e-6:
                for pos in {k * 10, -k * 10}:
                    if k % 5 == 0:
                        gl.glColor3f(0.36, 0.38, 0.42)
                    else:
                        gl.glColor3f(0.25, 0.26, 0.29)
                    if eixo_x:
                        gl.glVertex3f(pos, y0, z)
                        gl.glVertex3f(pos, y1, z)
                    else:
                        gl.glVertex3f(x0, pos, z)
                        gl.glVertex3f(x1, pos, z)
                k += 1
        gl.glEnd()

        # borda da mesa
        gl.glLineWidth(2.0)
        gl.glColor3f(0.0, 0.68, 0.61)
        gl.glBegin(gl.GL_LINE_LOOP)
        gl.glVertex3f(x0, y0, z)
        gl.glVertex3f(x1, y0, z)
        gl.glVertex3f(x1, y1, z)
        gl.glVertex3f(x0, y1, z)
        gl.glEnd()

        # eixos no canto: X vermelho, Y verde, Z azul
        tam = max(min(w, d) * 0.12, 10)
        gl.glLineWidth(3.0)
        gl.glBegin(gl.GL_LINES)
        for i, fim in enumerate(((x0 + tam, y0, 0.2), (x0, y0 + tam, 0.2), (x0, y0, tam))):
            gl.glColor3f(*CORES_EIXOS[i])
            gl.glVertex3f(x0, y0, 0.2)
            gl.glVertex3f(*fim)
        gl.glEnd()
        gl.glLineWidth(1.0)

    def _desenhar_peca(self, m):
        e = self._gpu.get(id(m))
        if e is None or e[3] == 0:
            return
        vbo, qtd = e[2], e[3]
        r, g, b, _ = self.cor.getRgbF()
        if len(self.cena.pecas) > 1 and m is not self.sel and not self._sem_controles:
            r, g, b = r * 0.72, g * 0.72, b * 0.72    # as não selecionadas ficam um pouco mais escuras
        mn, mx = self._caixa(m)
        if self.mostrar_mesa and self.fora_da_mesa(mn, mx):
            # fora da mesa: deixa avermelhado, como nos fatiadores
            r, g, b = r * 0.45 + 0.55, g * 0.45 + 0.12, b * 0.45 + 0.12

        gl.glPushMatrix()
        if m is self.sel and self._prev is not None:
            gl.glMultMatrixf(np.ascontiguousarray(self._prev["G"].T, dtype=np.float32))

        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo[0])
        gl.glVertexPointer(3, gl.GL_FLOAT, 0, None)
        gl.glEnableClientState(gl.GL_NORMAL_ARRAY)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo[1])
        gl.glNormalPointer(gl.GL_FLOAT, 0, None)

        if self.modo in (0, 2):  # sólido
            gl.glEnable(gl.GL_LIGHTING)
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
            if self.modo == 2:
                gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
                gl.glPolygonOffset(1.0, 1.0)
            gl.glColor3f(r, g, b)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, qtd)
            gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)

        if self.modo in (1, 2):  # malha
            gl.glDisable(gl.GL_LIGHTING)
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
            gl.glLineWidth(1.0)
            if self.modo == 1:
                gl.glColor3f(r, g, b)
            else:
                gl.glColor3f(r * 0.45, g * 0.45, b * 0.45)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, qtd)
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
        gl.glDisableClientState(gl.GL_NORMAL_ARRAY)
        gl.glDisable(gl.GL_LIGHTING)
        gl.glPopMatrix()

    @staticmethod
    def _linhas_caixa(mn, mx):
        cantos = [np.array([x, y, z]) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
        gl.glBegin(gl.GL_LINES)
        for i in range(8):
            for j in range(i + 1, 8):
                if bin(i ^ j).count("1") == 1:
                    gl.glVertex3f(*cantos[i])
                    gl.glVertex3f(*cantos[j])
        gl.glEnd()

    def _desenhar_selecao(self):
        if self.sel is None or len(self.cena.pecas) < 2 or self.ferramenta == "escala":
            return
        gl.glDisable(gl.GL_LIGHTING)
        gl.glColor3f(*COR_HOVER)
        gl.glLineWidth(1.5)
        mn, mx = self._caixa()
        self._linhas_caixa(mn, mx)
        gl.glLineWidth(1.0)

    def _desenhar_medidas(self):
        if self.ferramenta != "medir" or not self._medidas:
            return
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_LIGHTING)
        gl.glColor3f(*COR_HOVER)
        if len(self._medidas) == 2:
            gl.glLineWidth(3.0)
            gl.glBegin(gl.GL_LINES)
            gl.glVertex3f(*self._medidas[0])
            gl.glVertex3f(*self._medidas[1])
            gl.glEnd()
        gl.glPointSize(11.0)
        gl.glBegin(gl.GL_POINTS)
        for p in self._medidas:
            gl.glVertex3f(*p)
        gl.glEnd()
        gl.glPointSize(1.0)
        gl.glLineWidth(1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)

    # ---- controles arrastáveis ----
    @staticmethod
    def _raio_controle(h):
        return max(float(np.linalg.norm(h)) * 1.05, 8.0)

    def _alcas(self):
        """Lista dos controles da peça selecionada: (tipo, id, pontos)."""
        if self.sel is None or self.ferramenta not in ("mover", "girar", "escala"):
            return []
        mn, mx = self._caixa()
        c, h = (mn + mx) / 2, (mx - mn) / 2
        R = self._raio_controle(h)
        E = np.identity(3)
        alcas = []
        if self.ferramenta == "mover":
            comp = max(h[0], h[1]) + R * 0.45
            for w in (0, 1):
                fim = c + E[w] * comp
                alcas.append(("seta", f"m{w}", (c, fim, fim + E[w] * comp * self.PONTA)))
            alcas.append(("ponto", "mxy", (c,)))
        elif self.ferramenta == "girar":
            ang = np.linspace(0, 2 * np.pi, 97)
            for w in range(3):
                u, v = [k for k in range(3) if k != w]
                pts = [c + R * 0.75 * (math.cos(a) * E[u] + math.sin(a) * E[v]) for a in ang]
                alcas.append(("anel", f"r{w}", pts))
        elif self.ferramenta == "escala":
            margem = R * 0.18
            for w in range(3):
                for sg, s in ((1, "+"), (-1, "-")):
                    alcas.append(("ponto", f"s{w}{s}", (c + E[w] * sg * (h[w] + margem),)))
            alcas.append(("ponto", "su", (mx + margem * 0.6,)))
        return alcas

    def _alca_sob_mouse(self, m):
        mvp = self._mvp()
        melhor, menor = None, 1e9
        for tipo, ident, pts in self._alcas():
            tela = [self._tela(p, mvp) for p in pts]
            if any(t is None for t in tela):
                continue
            if tipo == "ponto":
                d = float(np.linalg.norm(m - tela[0])) - 4   # pontos têm prioridade
                limite = 14
            elif tipo == "seta":
                # a seta inteira vale: a linha (até a ponta) e a cabeça, com folga maior na cabeça
                d_linha = _dist_ponto_segmento(m, tela[0], tela[2])
                d_cabeca = _dist_ponto_segmento(m, tela[1], tela[2]) - 5
                d = min(d_linha, d_cabeca)
                limite = 10
            else:
                d = min(_dist_ponto_segmento(m, tela[i], tela[i + 1]) for i in range(len(tela) - 1))
                limite = 9
            if d < limite and d < menor:
                melhor, menor = ident, d
        return melhor

    def _cor_alca(self, ident):
        if ident == self._hover or (self._arr is not None and self._arr["id"] == ident):
            return COR_HOVER
        if ident in ("mxy", "su"):
            return (0.92, 0.92, 0.92)
        return CORES_EIXOS[int(ident[1])]

    def _desenhar_controles(self):
        alcas = self._alcas()
        if not alcas:
            return
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_LIGHTING)
        mn, mx = self._caixa()
        c = (mn + mx) / 2
        for tipo, ident, pts in alcas:
            cor = self._cor_alca(ident)
            gl.glColor3f(*cor)
            if tipo == "seta":
                a, b, ponta = pts
                gl.glLineWidth(4.0 if cor == COR_HOVER else 3.0)
                gl.glBegin(gl.GL_LINES)
                gl.glVertex3f(*a)
                gl.glVertex3f(*b)
                gl.glEnd()
                self._cone(b, ponta, cor)
            elif tipo == "anel":
                gl.glLineWidth(4.0 if cor == COR_HOVER else 2.5)
                gl.glBegin(gl.GL_LINE_STRIP)
                for p in pts:
                    gl.glVertex3f(*p)
                gl.glEnd()
            else:
                if ident.startswith("s"):   # linha do centro até o quadradinho
                    gl.glLineWidth(1.5)
                    gl.glBegin(gl.GL_LINES)
                    gl.glVertex3f(*c)
                    gl.glVertex3f(*pts[0])
                    gl.glEnd()
                gl.glPointSize(15.0 if cor == COR_HOVER else 12.0)
                gl.glBegin(gl.GL_POINTS)
                gl.glVertex3f(*pts[0])
                gl.glEnd()
        if self.ferramenta == "escala":   # caixa em volta da peça
            gl.glColor3f(0.75, 0.75, 0.75)
            gl.glLineWidth(1.0)
            self._linhas_caixa(mn, mx)
        gl.glPointSize(1.0)
        gl.glLineWidth(1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)

    @staticmethod
    def _cone(base, ponta, cor):
        eixo = ponta - base
        comp = float(np.linalg.norm(eixo))
        if comp < 1e-6:
            return
        d = eixo / comp
        aux = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = _normalizar(np.cross(d, aux))
        v = np.cross(d, u)
        raio = comp * 0.30
        gl.glColor3f(*cor)
        gl.glBegin(gl.GL_TRIANGLE_FAN)
        gl.glVertex3f(*ponta)
        for k in range(17):
            t = 2 * math.pi * k / 16
            gl.glVertex3f(*(base + raio * (math.cos(t) * u + math.sin(t) * v)))
        gl.glEnd()

    def _quantidade_no_eixo(self, mvp, c, eixo, comp, m0, m):
        """Quanto o mouse andou (em mm) na direção de um eixo, olhando a tela."""
        p0, p1 = self._tela(c, mvp), self._tela(c + eixo * comp, mvp)
        if p0 is None or p1 is None:
            return 0.0
        a = p1 - p0
        la2 = float(np.dot(a, a))
        if la2 < 9:
            return 0.0
        return float(np.dot(m - m0, a)) / la2 * comp

    def _angulo_plano(self, m, mvp, c, w):
        """Ângulo (graus) do ponto do mouse no plano do anel do eixo w, ou None se o anel está de lado."""
        o, d = self._raio_mouse(m, mvp)
        if abs(d[w]) < 0.12:
            return None
        t = (c[w] - o[w]) / d[w]
        if t <= 0:
            return None
        p = o + d * t - c
        u, v = ((1, 2), (2, 0), (0, 1))[w]
        return math.degrees(math.atan2(p[v], p[u]))

    @staticmethod
    def _angulo_tela(m, pc):
        return math.degrees(math.atan2(-(m[1] - pc[1]), m[0] - pc[0]))

    def _iniciar_arrasto(self, ident, m, z_plano=None):
        mod = self.sel
        mvp = self._mvp()
        a = {"id": ident, "m0": m, "mvp": mvp, "olho": self._olho(), "R0": mod.R.copy(),
             "S0": mod.S.copy(), "pos0": mod.pos.copy(), "mn": mod.mn.copy(), "mx": mod.mx.copy(),
             "z": z_plano, "acum": 0.0, "ang_ult": None}
        c = (mod.mn + mod.mx) / 2
        if ident == "mxy":
            a["z"] = c[2]
        if ident.startswith("r"):
            w = int(ident[1])
            ang = self._angulo_plano(m, mvp, c, w)
            a["no_plano"] = ang is not None
            if ang is None:
                pc = self._tela(c, mvp)
                ang = self._angulo_tela(m, pc) if pc is not None else 0.0
            a["ang_ult"] = ang
        self._arr = a

    def _arrastar(self, m, shift):
        a, mod = self._arr, self.sel
        ident, mvp = a["id"], a["mvp"]
        c = (a["mn"] + a["mx"]) / 2
        h = (a["mx"] - a["mn"]) / 2
        R = self._raio_controle(h)
        E = np.identity(3)
        R2, S2, pos2 = a["R0"], a["S0"].copy(), a["pos0"].copy()
        texto = ""

        if ident in ("m0", "m1"):
            w = int(ident[1])
            pos2[w] += self._quantidade_no_eixo(mvp, c, E[w], R, a["m0"], m)
        elif ident in ("mxy", "corpo"):
            p0 = self._ponto_no_plano(a["m0"], mvp, a["z"])
            p1 = self._ponto_no_plano(m, mvp, a["z"])
            if p0 is not None and p1 is not None:
                pos2 = pos2 + (p1 - p0)[:2]
        elif ident.startswith("r"):
            w = int(ident[1])
            if a["no_plano"]:
                # ângulo medido no plano do próprio anel (exato, mesmo em perspectiva)
                ang = self._angulo_plano(m, mvp, c, w)
                sinal = 1.0
            else:
                # anel visto de lado: usa o ângulo na tela
                pc = self._tela(c, mvp)
                ang = self._angulo_tela(m, pc) if pc is not None else None
                sinal = 1.0 if np.dot(E[w], a["olho"] - c) >= 0 else -1.0
            if ang is not None:
                passo = (ang - a["ang_ult"] + 180) % 360 - 180
                a["acum"] += passo
                a["ang_ult"] = ang
            graus = a["acum"] * sinal
            if not shift:
                graus = round(graus / 5) * 5     # de 5 em 5 graus (Shift = livre)
            R2 = matriz_rotacao(w, graus) @ a["R0"]
            texto = f"{'XYZ'[w]}: {num(graus, 0)}°"
        elif ident == "su":
            pc = self._tela(c, mvp)
            if pc is not None:
                f = np.linalg.norm(m - pc) / max(np.linalg.norm(a["m0"] - pc), 1.0)
                S2 = a["S0"] * max(f, 0.001)
        elif ident.startswith("s"):
            w = int(ident[1])
            sg = 1.0 if ident[2] == "+" else -1.0
            andou = self._quantidade_no_eixo(mvp, c, E[w] * sg, R, a["m0"], m)
            hw = max(h[w], 1e-6)
            f = max(hw + andou, hw * 0.001) / hw
            if self.manter_proporcao:
                S2 = a["S0"] * f
            else:
                S2[mod.eixo_local(w, a["R0"])] *= f

        self._prev = mod.previa(R2, S2, pos2)
        self._novo = (R2, S2, pos2)
        dim = self._prev["dim"]
        if not texto:
            if ident.startswith("m") or ident == "corpo":
                cx = (self._prev["mn"] + self._prev["mx"]) / 2
                texto = f"X {num(cx[0] + self.mesa[0] / 2)}   Y {num(cx[1] + self.mesa[1] / 2)}"
            else:
                texto = f"{num(dim[0])} × {num(dim[1])} × {num(dim[2])} mm"
        self.lb_arrasto.setText(texto)
        self.lb_arrasto.adjustSize()
        self.lb_arrasto.move(int(m[0]) + 18, int(m[1]) + 18)
        self.lb_arrasto.show()
        self.previa_mudou.emit(dim)
        self.update()

    def _terminar_arrasto(self):
        novo = self._novo
        if novo is not None and self.sel is not None:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self.cena.registrar()
                self.sel.definir(*novo)
            finally:
                QApplication.restoreOverrideCursor()
        self._arr = self._prev = self._novo = None
        self.lb_arrasto.hide()
        if novo is not None:
            self._medidas = []
            self._atualizar_medida()
            self.alterado.emit()
        self.update()

    # ---- mouse ----
    def mousePressEvent(self, e):
        p = e.position()
        m = np.array([p.x(), p.y()])
        self._ultimo = p
        self._inicio_clique = p
        self._moveu = False
        self._botao = e.button()
        if e.button() != Qt.MouseButton.LeftButton or not self.cena.pecas:
            return
        if self.ferramenta in ("mover", "girar", "escala") and self.sel is not None:
            alca = self._alca_sob_mouse(m)
            if alca:
                self._iniciar_arrasto(alca, m)
                return
        toque = self._tocar(m)
        if self.ferramenta == "medir":
            if toque is not None:
                if len(self._medidas) >= 2:
                    self._medidas = []
                self._medidas.append(toque[1])
                self._atualizar_medida()
                self._botao = None
                self.update()
            return
        if toque is not None:
            peca, ponto = toque
            if peca is not self.sel:
                self.cena.selecionada = peca
                self.selecao_mudou.emit()
                self.update()
            if self.ferramenta == "mover":   # clicar e arrastar a própria peça
                self._iniciar_arrasto("corpo", m, z_plano=float(ponto[2]))
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, e):
        if self._arr is not None:
            self._terminar_arrasto()
            self.unsetCursor()
        elif e.button() == Qt.MouseButton.RightButton and not getattr(self, "_moveu", True):
            # clique direito sem arrastar: seleciona o que está embaixo e abre o menu
            p = e.position()
            toque = self._tocar(np.array([p.x(), p.y()])) if self.cena.pecas else None
            if toque is not None and toque[0] is not self.sel:
                self.cena.selecionada = toque[0]
                self.selecao_mudou.emit()
                self.update()
            self._botao = None
            self.menu_pedido.emit(e.globalPosition().toPoint())
            return
        self._botao = None

    def mouseMoveEvent(self, e):
        p = e.position()
        m = np.array([p.x(), p.y()])
        if self._arr is not None:
            shift = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._arrastar(m, shift)
            return
        if self._botao is None:   # só passando o mouse: destacar controle
            if self.ferramenta in ("mover", "girar", "escala"):
                alca = self._alca_sob_mouse(m)
                if alca != self._hover:
                    self._hover = alca
                    if alca:
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                    else:
                        self.unsetCursor()
                    self.update()
            return
        if self._ultimo is None:
            return
        if not self._moveu:
            ini = self._inicio_clique
            if abs(p.x() - ini.x()) + abs(p.y() - ini.y()) < 5:
                return
            self._moveu = True
        dx, dy = p.x() - self._ultimo.x(), p.y() - self._ultimo.y()
        self._ultimo = p
        if self._botao == Qt.MouseButton.LeftButton:
            self.yaw -= dx * 0.4
            self.pitch = max(-89.0, min(89.0, self.pitch + dy * 0.4))
        else:  # botão direito ou do meio: arrastar a vista
            olho = self._olho()
            f = _normalizar(self.alvo - olho)
            s = _normalizar(np.cross(f, np.array([0.0, 0.0, 1.0])))
            u = np.cross(s, f)
            esc = 2 * self.dist * math.tan(math.radians(self.FOV / 2)) / max(self.height(), 1)
            self.alvo = self.alvo + (-dx * s + dy * u) * esc
        self.update()

    def wheelEvent(self, e):
        passos = e.angleDelta().y() / 120.0
        self.dist = max(1.0, min(self.dist * (0.85 ** passos), 100000.0))
        self.update()

    def mouseDoubleClickEvent(self, e):
        if self._arr is None and self.ferramenta != "medir":
            self.enquadrar()


# ---------------------------------------------------------------------------
#  Biblioteca (pastas com miniaturas)
# ---------------------------------------------------------------------------
class SinaisMiniatura(QObject):
    pronta = Signal(str, str)   # arquivo, png ("" = erro)


class TrabalhoMiniatura(QRunnable):
    """Gera a miniatura (e as medidas) em segundo plano, sem travar a janela."""

    def __init__(self, caminho, destino, cor, sinais):
        super().__init__()
        self.caminho, self.destino, self.cor, self.sinais = caminho, destino, cor, sinais

    def run(self):
        png = ""
        try:
            tris = carregar_para_miniatura(self.caminho)
            img = miniatura(tris, TAM_MINIATURA, self.cor)
            h, w, _ = img.shape
            q = QImage(img.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
            if q.save(self.destino, "PNG"):
                png = self.destino
            pts = tris.reshape(-1, 3)
            info = {"dim": [float(x) for x in (pts.max(0) - pts.min(0))], "tri": int(len(tris))}
            with open(os.path.splitext(self.destino)[0] + ".json", "w", encoding="utf-8") as f:
                json.dump(info, f)
        except Exception:
            png = png or ""
        try:
            self.sinais.pronta.emit(self.caminho, png)
        except RuntimeError:
            pass


class Miniaturas(QObject):
    """Faz e guarda as miniaturas; usado pela tela Biblioteca e pela aba Biblioteca."""
    pronta = Signal(str, str)
    cache_limpo = Signal()

    def __init__(self, cor_atual):
        super().__init__()
        self.cor_atual = cor_atual
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(max(1, min(3, (os.cpu_count() or 2) - 1)))
        self._sinais = SinaisMiniatura()
        self._sinais.pronta.connect(self._chegou)
        self._pendentes = set()

    def caminho_cache(self, caminho):
        try:
            st = os.stat(caminho)
        except OSError:
            return None
        chave = f"{caminho}|{st.st_mtime_ns}|{st.st_size}|{self.cor_atual().name()}|{TAM_MINIATURA}|v2"
        return os.path.join(pasta_dados("miniaturas"), hashlib.sha1(chave.encode("utf-8", "ignore")).hexdigest() + ".png")

    def pedir(self, caminho):
        """Devolve o PNG se já existe ("" se não dá para ler); senão manda fazer e devolve None."""
        destino = self.caminho_cache(caminho)
        if destino is None:
            return ""
        if os.path.isfile(destino):
            return destino
        if caminho not in self._pendentes:
            self._pendentes.add(caminho)
            cor = tuple(self.cor_atual().getRgbF()[:3])
            self.pool.start(TrabalhoMiniatura(caminho, destino, cor, self._sinais))
        return None

    def info(self, caminho):
        destino = self.caminho_cache(caminho)
        if destino is None:
            return None
        try:
            with open(os.path.splitext(destino)[0] + ".json", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def parar(self):
        self.pool.clear()
        self._pendentes.clear()

    def tamanho_cache(self):
        """(quantidade de miniaturas, bytes ocupados)"""
        pasta = pasta_dados("miniaturas")
        qtd = total = 0
        try:
            for e in os.scandir(pasta):
                if e.is_file():
                    total += e.stat().st_size
                    qtd += e.name.endswith(".png")
        except OSError:
            pass
        return qtd, total

    def limpar_cache(self):
        self.parar()
        self.pool.waitForDone(3000)
        pasta = pasta_dados("miniaturas")
        for e in os.scandir(pasta):
            try:
                if e.is_file():
                    os.remove(e.path)
            except OSError:
                pass
        self.cache_limpo.emit()

    def _chegou(self, caminho, png):
        self._pendentes.discard(caminho)
        self.pronta.emit(caminho, png)


class Pastas(QObject):
    """Lista de pastas da biblioteca (salva nas configurações)."""
    mudaram = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        try:
            dados = json.loads(str(cfg.value("biblioteca_pastas", "[]")))
            self.lista = [p for p in dados if isinstance(p, str)]
        except (ValueError, TypeError):
            self.lista = []

    def _salvar(self):
        self.cfg.setValue("biblioteca_pastas", json.dumps(self.lista))

    def adicionar(self, pasta):
        pasta = os.path.normpath(pasta)
        if pasta not in self.lista:
            self.lista.append(pasta)
            self._salvar()
        self.mudaram.emit()
        return pasta

    def remover(self, pasta):
        self.lista = [p for p in self.lista if p != pasta]
        self._salvar()
        self.mudaram.emit()


# ---- leitura das pastas (sem janela) ----
def _e_modelo(nome):
    return nome.lower().endswith(EXTENSOES_ABRIR)


def conteudo_da_pasta(pasta):
    """Subpastas e modelos que estão direto dentro de uma pasta (sem descer nas subpastas)."""
    subpastas, modelos = [], []
    try:
        with os.scandir(pasta) as it:
            for e in it:
                if e.name.startswith((".", "$")):
                    continue
                try:
                    if e.is_dir(follow_symlinks=False):
                        subpastas.append(e.path)
                    elif e.is_file() and _e_modelo(e.name):
                        modelos.append(e.path)
                except OSError:
                    pass
    except OSError:
        pass
    chave = lambda p: os.path.basename(p).lower()
    return sorted(subpastas, key=chave), sorted(modelos, key=chave)


def modelos_dentro(pasta, limite=5000):
    """Todos os modelos de uma pasta e das subpastas dela (os da própria pasta primeiro)."""
    achados = []
    for raiz, dirs, nomes in os.walk(pasta):
        dirs[:] = sorted((d for d in dirs if not d.startswith((".", "$"))), key=str.lower)
        for n in sorted(nomes, key=str.lower):
            if _e_modelo(n):
                achados.append(os.path.join(raiz, n))
                if len(achados) >= limite:
                    return achados
    return achados


def resumo_da_pasta(pasta, limite=5000):
    """(quantidade de modelos, 4 exemplos para a colagem, bytes, subpastas diretas)"""
    modelos = modelos_dentro(pasta, limite)
    total = 0
    for m in modelos:
        try:
            total += os.path.getsize(m)
        except OSError:
            pass
    subpastas, _ = conteudo_da_pasta(pasta)
    return len(modelos), modelos[:4], total, len(subpastas)


# ---- ícones ----
def _icone_texto(texto, cor="#5a5f66"):
    pm = QPixmap(TAM_MINIATURA, TAM_MINIATURA)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#22252a"))
    m = TAM_MINIATURA // 16
    p.drawRoundedRect(m, m, TAM_MINIATURA - 2 * m, TAM_MINIATURA - 2 * m, m * 2, m * 2)
    p.setPen(QColor(cor))
    f = QFont()
    f.setPointSize(TAM_MINIATURA // 6)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, texto)
    p.end()
    return QIcon(pm)


def pixmap_pasta(pngs, tam=TAM_MINIATURA):
    """Desenha uma pasta com as miniaturas de até 4 modelos de dentro (1, 2, 3 ou 4 espaços)."""
    pm = QPixmap(tam, tam)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    m = tam * 0.06
    aba_alt = tam * 0.09
    raio = tam * 0.05
    amarelo = QColor("#d4a72c")
    # aba da pasta
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(amarelo)
    p.drawRoundedRect(QRectF(m, m + tam * 0.04, tam * 0.42, aba_alt * 1.8), raio, raio)
    # corpo
    corpo = QRectF(m, m + tam * 0.04 + aba_alt, tam - 2 * m, tam - 2 * m - tam * 0.04 - aba_alt)
    p.setBrush(QColor("#3b3322"))
    p.setPen(QPen(amarelo, max(2.0, tam / 64)))
    p.drawRoundedRect(corpo, raio, raio)
    # miniaturas: 1 = inteira, 2 = lado a lado, 3 = uma grande + duas empilhadas, 4 = grade 2x2
    folga = tam * 0.04
    x0, y0 = corpo.x() + folga, corpo.y() + folga
    larg, alt = corpo.width() - 2 * folga, corpo.height() - 2 * folga
    meia_l, meia_a = (larg - folga) / 2, (alt - folga) / 2
    qtd = min(len(pngs), 4)
    if qtd <= 1:
        celulas = [QRectF(x0, y0, larg, alt)]
    elif qtd == 2:
        celulas = [QRectF(x0, y0, meia_l, alt), QRectF(x0 + meia_l + folga, y0, meia_l, alt)]
    elif qtd == 3:
        celulas = [QRectF(x0, y0, meia_l, alt),
                   QRectF(x0 + meia_l + folga, y0, meia_l, meia_a),
                   QRectF(x0 + meia_l + folga, y0 + meia_a + folga, meia_l, meia_a)]
    else:
        celulas = [QRectF(x0 + (i % 2) * (meia_l + folga), y0 + (i // 2) * (meia_a + folga), meia_l, meia_a)
                   for i in range(4)]
    p.setPen(Qt.PenStyle.NoPen)
    for i, cel in enumerate(celulas):
        p.setBrush(QColor("#17191c"))
        p.drawRoundedRect(cel, raio * 0.6, raio * 0.6)
        if i < len(pngs) and pngs[i]:
            img = QPixmap(pngs[i])
            if not img.isNull():
                img = img.scaled(int(cel.width()), int(cel.height()), Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(int(cel.x() + (cel.width() - img.width()) / 2),
                             int(cel.y() + (cel.height() - img.height()) / 2), img)
    p.end()
    return pm


# ---- menus ----
def _menu_arquivos(parent, caminhos, abrir, adicionar):
    """Menu do botão direito em modelos da biblioteca."""
    menu = QMenu(parent)
    a_abrir = menu.addAction(T("Abrir") if len(caminhos) == 1 else T("Abrir {n} modelos juntos", n=len(caminhos)))
    a_add = menu.addAction(T("Adicionar à mesa"))
    a_fat = None
    if sys.platform == "win32" and all(c.lower().endswith(FORMATOS_FATIADOR) for c in caminhos):
        a_fat = menu.addAction(T("Abrir no fatiador ({f})", f=ler_fatiador()[0]))
    a_pasta = None
    if len(caminhos) == 1 and sys.platform == "win32":
        menu.addSeparator()
        a_pasta = menu.addAction(T("Mostrar na pasta"))
    if EXTRAS_MENU_ARQUIVOS:
        menu.addSeparator()
        _aplicar_extras(EXTRAS_MENU_ARQUIVOS, menu, list(caminhos))
    escolha = menu.exec(QCursor.pos())
    if escolha is a_abrir:
        abrir(caminhos)
    elif escolha is a_add:
        adicionar(caminhos)
    elif a_fat is not None and escolha is a_fat:
        abrir_no_fatiador(parent, caminhos)
    elif a_pasta is not None and escolha is a_pasta:
        mostrar_na_pasta(caminhos[0])


def _confirmar_muitos(parent, n):
    if n <= 20:
        return True
    r = QMessageBox.question(parent, nome_app(),
                             T("Abrir {n} modelos de uma vez? Isso pode demorar um pouco.", n=num(n, 0)),
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                             QMessageBox.StandardButton.No)
    return r == QMessageBox.StandardButton.Yes


def _menu_pasta(parent, pasta, entrar, abrir, adicionar):
    """Menu do botão direito numa pasta da biblioteca."""
    menu = QMenu(parent)
    a_entrar = menu.addAction(T("Entrar na pasta"))
    menu.addSeparator()
    a_abrir = menu.addAction(T("Abrir todos juntos"))
    a_add = menu.addAction(T("Adicionar todos à mesa"))
    a_explorer = None
    if sys.platform == "win32":
        menu.addSeparator()
        a_explorer = menu.addAction(T("Mostrar no Explorer"))
    escolha = menu.exec(QCursor.pos())
    if escolha is a_entrar:
        entrar(pasta)
    elif escolha in (a_abrir, a_add):
        modelos = modelos_dentro(pasta)
        if modelos and _confirmar_muitos(parent, len(modelos)):
            (abrir if escolha is a_abrir else adicionar)(modelos)
    elif a_explorer is not None and escolha is a_explorer:
        abrir_no_explorer(pasta)


def mostrar_na_pasta(caminho):
    if sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{os.path.normpath(caminho)}"')


def abrir_no_explorer(pasta):
    if sys.platform == "win32":
        subprocess.Popen(["explorer", os.path.normpath(pasta)])


PAPEL_TIPO = Qt.ItemDataRole.UserRole + 1   # "modelo" ou "pasta"


class NavegadorPastas:
    """
    Lógica de navegação compartilhada pela tela Biblioteca e pela aba Biblioteca:
    raiz escolhida, pasta atual, itens (pastas primeiro, depois modelos) e miniaturas.
    A classe que usa precisa ter: self.lista (QListWidget), self.mini, self.pastas, self.busca.
    """
    MAX_ARQUIVOS = 3000

    def _iniciar_navegacao(self):
        self.atual = None          # None = "Todas as pastas" (mostra cada pasta da biblioteca)
        self.itens = {}            # caminho do modelo -> item
        self.pastas_itens = {}     # caminho da pasta -> (item, exemplos)
        self._icone_espera = _icone_texto("…")
        self._icone_erro = _icone_texto("?", "#ff7a7a")
        self._em_busca = False
        self._timer_busca = QTimer()
        self._timer_busca.setSingleShot(True)
        self._timer_busca.setInterval(300)
        self._timer_busca.timeout.connect(self.carregar)

    # --- onde estou ---
    def raizes(self):
        return list(self.pastas.lista)

    def raiz_de(self, caminho):
        if caminho is None:
            return None
        norm = os.path.normcase(os.path.normpath(caminho))
        for r in self.raizes():
            rn = os.path.normcase(os.path.normpath(r))
            if norm == rn or norm.startswith(rn + os.sep):
                return r
        return None

    def pode_voltar(self):
        if self.atual is None:
            return False
        if self.raiz_de(self.atual) == self.atual:
            return len(self.raizes()) > 1 and self.raiz_escolhida() is None
        return True

    def pai(self):
        if self.atual is None:
            return None
        if self.raiz_de(self.atual) == self.atual:
            return None
        return os.path.dirname(self.atual)

    def entrar(self, pasta):
        self.atual = pasta
        self.busca.blockSignals(True)
        self.busca.clear()
        self.busca.blockSignals(False)
        self.carregar()

    def voltar(self):
        if self.pode_voltar():
            self.entrar(self.pai())

    def _busca_mudou(self, *_):
        self._timer_busca.start()

    def _ligar_atalhos_voltar(self):
        """Backspace e o botão lateral "voltar" do mouse também voltam uma pasta."""
        self.lista.installEventFilter(self)
        self.lista.viewport().installEventFilter(self)

    def _filtro_voltar(self, obj, ev):
        tipo = ev.type()
        if tipo == QEvent.Type.KeyPress and ev.key() == Qt.Key.Key_Backspace and not self._em_busca:
            self.voltar()
            return True
        if tipo == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.BackButton:
            self.voltar()
            return True
        return False

    def _atualizar_botao_voltar(self):
        self.b_voltar.setEnabled(self.pode_voltar() and not self._em_busca)

    # --- preencher a lista ---
    def _adicionar_pasta(self, pasta, nome=None):
        qtd, exemplos, _total, _subs = resumo_da_pasta(pasta, 2000)
        if qtd == 0:
            return None
        texto = f"{nome or os.path.basename(pasta.rstrip(chr(92) + '/')) or pasta}\n{T('Modelos: {n}', n=num(qtd, 0))}"
        it = QListWidgetItem(texto)
        it.setData(Qt.ItemDataRole.UserRole, pasta)
        it.setData(PAPEL_TIPO, "pasta")
        it.setToolTip(pasta)
        self.lista.addItem(it)
        self.pastas_itens[pasta] = (it, exemplos)
        for ex in exemplos:
            self.mini.pedir(ex)
        self._pintar_pasta(pasta)
        return it

    def _pintar_pasta(self, pasta):
        it, exemplos = self.pastas_itens[pasta]
        pngs = []
        for ex in exemplos:
            png = self.mini.caminho_cache(ex)
            pngs.append(png if png and os.path.isfile(png) else None)
        it.setIcon(QIcon(pixmap_pasta(pngs)))

    def _adicionar_modelo(self, caminho):
        it = QListWidgetItem(self._icone_espera, os.path.basename(caminho))
        it.setData(Qt.ItemDataRole.UserRole, caminho)
        it.setData(PAPEL_TIPO, "modelo")
        it.setToolTip(caminho)
        self.lista.addItem(it)
        self.itens[caminho] = it
        png = self.mini.pedir(caminho)
        if png == "":
            it.setIcon(self._icone_erro)
        elif png:
            it.setIcon(QIcon(png))

    def _preencher(self):
        """Monta a lista; devolve a quantidade de modelos mostrados."""
        self.lista.clear()
        self.itens = {}
        self.pastas_itens = {}
        termo = self.busca.text().strip().lower()
        self._em_busca = bool(termo)
        if self.atual is not None and not os.path.isdir(self.atual):
            self.atual = self.raiz_escolhida()
        if self.atual is None and self.raiz_escolhida() is not None:
            self.atual = self.raiz_escolhida()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if termo:   # busca: procura em todas as subpastas e mostra só os modelos achados
                base = [self.atual] if self.atual else self.raizes()
                n = 0
                for b in base:
                    for c in modelos_dentro(b, self.MAX_ARQUIVOS * 4):
                        if termo in os.path.basename(c).lower():
                            self._adicionar_modelo(c)
                            n += 1
                            if n >= self.MAX_ARQUIVOS:
                                return n
                return n
            if self.atual is None:   # "Todas as pastas": cada pasta da biblioteca vira um item
                for r in self.raizes():
                    if os.path.isdir(r):
                        self._adicionar_pasta(r)
                return 0
            subpastas, modelos = conteudo_da_pasta(self.atual)
            for s in subpastas:
                self._adicionar_pasta(s)
            for c in modelos[:self.MAX_ARQUIVOS]:
                self._adicionar_modelo(c)
            return len(modelos)
        finally:
            QApplication.restoreOverrideCursor()

    def _miniatura_chegou(self, caminho, png):
        it = self.itens.get(caminho)
        if it is not None:
            it.setIcon(QIcon(png) if png else self._icone_erro)
        for pasta, (_it, exemplos) in list(self.pastas_itens.items()):
            if caminho in exemplos:
                self._pintar_pasta(pasta)

    def _duplo_clique(self, it):
        tipo = it.data(PAPEL_TIPO)
        if tipo == "pasta":
            self.entrar(it.data(Qt.ItemDataRole.UserRole))
        else:
            self.abrir_pedido.emit([it.data(Qt.ItemDataRole.UserRole)])

    def _menu(self, pos):
        it = self.lista.itemAt(pos)
        if it is None:
            return
        if it.data(PAPEL_TIPO) == "pasta":
            self.lista.clearSelection()
            it.setSelected(True)
            _menu_pasta(self, it.data(Qt.ItemDataRole.UserRole), self.entrar,
                        self.abrir_pedido.emit, self.adicionar_pedido.emit)
            return
        if not it.isSelected():
            self.lista.clearSelection()
            it.setSelected(True)
        caminhos = [i.data(Qt.ItemDataRole.UserRole) for i in self.lista.selectedItems()
                    if i.data(PAPEL_TIPO) == "modelo"]
        if caminhos:
            _menu_arquivos(self, caminhos, self.abrir_pedido.emit, self.adicionar_pedido.emit)

    def _caminho_html(self):
        """Caminho clicável: Pasta › Subpasta › Atual"""
        if self._em_busca:
            return f"<b>{T('Resultados da busca')}</b>"
        if self.atual is None:
            return f"<b>{T('Todas as pastas')}</b>"
        raiz = self.raiz_de(self.atual) or self.atual
        partes = []
        if len(self.raizes()) > 1 and self.raiz_escolhida() is None:
            partes.append(("*", T("Todas as pastas")))
        partes.append((raiz, os.path.basename(raiz.rstrip("\\/")) or raiz))
        rel = os.path.relpath(self.atual, raiz)
        if rel != ".":
            acumulado = raiz
            for pedaco in rel.split(os.sep):
                acumulado = os.path.join(acumulado, pedaco)
                partes.append((acumulado, pedaco))
        html = []
        for i, (destino, nome) in enumerate(partes):
            nome = nome.replace("&", "&amp;").replace("<", "&lt;")
            if i == len(partes) - 1:
                html.append(f"<b>{nome}</b>")
            else:
                html.append(f'<a href="{destino}" style="color:{COR_DESTAQUE}; text-decoration:none">{nome}</a>')
        return "  ›  ".join(html)

    def _caminho_clicado(self, destino):
        self.entrar(None if destino == "*" else destino)


class Biblioteca(QWidget, NavegadorPastas):
    """Tela Biblioteca: pastas, grade de miniaturas (pastas e modelos) e painel de detalhes."""
    abrir_pedido = Signal(list)
    adicionar_pedido = Signal(list)

    def __init__(self, pastas, miniaturas):
        super().__init__()
        self.pastas = pastas
        self.mini = miniaturas
        self._carregada = False
        self._escolher = None
        self._detalhe = None
        self._montar()
        cfg = self.pastas.cfg
        self.grupo_modo.button(1 if str(cfg.value("biblioteca_modo", "miniaturas")) == "lista" else 0).setChecked(True)
        self.sl_tam.blockSignals(True)
        self.sl_tam.setValue(int(cfg.value("biblioteca_tamanho", 128, type=int)))
        self.sl_tam.blockSignals(False)
        self._aplicar_visual()
        self._iniciar_navegacao()
        self._ligar_atalhos_voltar()
        self.mini.pronta.connect(self._miniatura_pronta)
        self.mini.cache_limpo.connect(self._cache_limpo)
        self.pastas.mudaram.connect(self._pastas_mudaram)
        self._preencher_pastas()

    # ---- tela ----
    def _montar(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        esq = QFrame()
        esq.setObjectName("cartao")
        esq.setFixedWidth(240)
        v = QVBoxLayout(esq)
        v.setContentsMargins(12, 10, 12, 12)
        titulo = QLabel(T("Pastas"))
        titulo.setObjectName("titulo")
        v.addWidget(titulo)
        self.lista_pastas = QListWidget()
        self.lista_pastas.currentRowChanged.connect(self._raiz_mudou)
        v.addWidget(self.lista_pastas, 1)
        linha = QHBoxLayout()
        b = QPushButton(T("Adicionar pasta…"))
        b.setObjectName("principal")
        b.clicked.connect(self.adicionar_pasta)
        linha.addWidget(b)
        b = QPushButton(T("Remover"))
        b.setToolTip(T("Remove a pasta da biblioteca (os arquivos não são apagados)"))
        b.clicked.connect(self.remover_pasta)
        linha.addWidget(b)
        v.addLayout(linha)
        linha_cache = QFrame()
        linha_cache.setObjectName("divisoria")
        v.addWidget(linha_cache)
        self.lb_cache = QLabel("")
        self.lb_cache.setObjectName("fraco")
        self.lb_cache.setWordWrap(True)
        v.addWidget(self.lb_cache)
        b = QPushButton(T("Limpar cache de miniaturas"))
        b.setToolTip(T("Apaga as miniaturas salvas. Elas são geradas de novo quando necessário."))
        b.clicked.connect(self.limpar_cache)
        v.addWidget(b)
        lay.addWidget(esq)

        meio = QVBoxLayout()
        meio.setSpacing(8)
        linha = QHBoxLayout()
        self.b_voltar = QToolButton()
        self.b_voltar.setText("←")
        self.b_voltar.setObjectName("navegar")
        self.b_voltar.setToolTip(T("Voltar para a pasta anterior"))
        self.b_voltar.clicked.connect(self.voltar)
        linha.addWidget(self.b_voltar)
        self.lb_caminho = QLabel("")
        self.lb_caminho.setTextFormat(Qt.TextFormat.RichText)
        self.lb_caminho.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.lb_caminho.linkActivated.connect(self._caminho_clicado)
        self.lb_caminho.setMinimumWidth(80)
        linha.addWidget(self.lb_caminho, 1)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText(T("Buscar por nome…"))
        self.busca.setClearButtonEnabled(True)
        self.busca.setFixedWidth(260)
        self.busca.textChanged.connect(self._busca_mudou)
        linha.addWidget(self.busca)
        self.lb_qtd = QLabel("")
        self.lb_qtd.setObjectName("fraco")
        linha.addWidget(self.lb_qtd)
        b = QPushButton(T("Atualizar"))
        b.clicked.connect(self.carregar)
        linha.addWidget(b)
        meio.addLayout(linha)

        # modo de exibição e tamanho (como no Explorer)
        linha = QHBoxLayout()
        linha.setSpacing(0)
        self.grupo_modo = QButtonGroup(self)
        for i, (texto, dica) in enumerate(((T("Miniaturas"), T("Mostrar como miniaturas")),
                                           (T("Lista"), T("Mostrar como lista")))):
            b = QToolButton()
            b.setText(texto)
            b.setToolTip(dica)
            b.setCheckable(True)
            b.setObjectName("segmento_esq" if i == 0 else "segmento_dir")
            self.grupo_modo.addButton(b, i)
            linha.addWidget(b)
        self.grupo_modo.idClicked.connect(lambda _i: self._aplicar_visual())
        linha.addSpacing(16)
        pequeno = QLabel("▫")
        pequeno.setObjectName("fraco")
        linha.addWidget(pequeno)
        linha.addSpacing(6)
        self.sl_tam = QSlider(Qt.Orientation.Horizontal)
        self.sl_tam.setRange(48, 256)
        self.sl_tam.setSingleStep(16)
        self.sl_tam.setPageStep(32)
        self.sl_tam.setFixedWidth(170)
        self.sl_tam.setToolTip(T("Tamanho das miniaturas (Ctrl + roda do mouse)"))
        self.sl_tam.valueChanged.connect(lambda _v: self._aplicar_visual())
        linha.addWidget(self.sl_tam)
        linha.addSpacing(6)
        grande = QLabel("◻")
        grande.setObjectName("fraco")
        grande.setStyleSheet("font-size: 17px;")
        linha.addWidget(grande)
        linha.addStretch(1)
        meio.addLayout(linha)

        self.pilha = QStackedWidget()
        vazio = QLabel(T("Nenhuma pasta na biblioteca.\nUse “Adicionar pasta…” para começar."))
        vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vazio.setStyleSheet("color: #8a8f96; font-size: 16px;")
        self.pilha.addWidget(vazio)
        self.lista = QListWidget()
        self.lista.setObjectName("grade")
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista.itemDoubleClicked.connect(self._duplo_clique)
        self.lista.currentItemChanged.connect(lambda it, _ant: self._mostrar_detalhes(it))
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu)
        self.pilha.addWidget(self.lista)
        meio.addWidget(self.pilha, 1)
        dica = QLabel(T("Duplo clique: abrir   ·   Botão direito: mais opções"))
        dica.setObjectName("fraco")
        meio.addWidget(dica)
        lay.addLayout(meio, 1)

        # painel de detalhes
        det = QFrame()
        det.setObjectName("cartao")
        det.setFixedWidth(280)
        v = QVBoxLayout(det)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)
        titulo = QLabel(T("Detalhes"))
        titulo.setObjectName("titulo")
        v.addWidget(titulo)
        self.det_img = QLabel()
        self.det_img.setFixedSize(254, 254)
        self.det_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.det_img.setObjectName("previa")
        v.addWidget(self.det_img)
        self.det_nome = QLabel("")
        self.det_nome.setObjectName("nome")
        self.det_nome.setWordWrap(True)
        v.addWidget(self.det_nome)
        self.det_pasta = QLabel("")
        self.det_pasta.setObjectName("fraco")
        self.det_pasta.setWordWrap(True)
        v.addWidget(self.det_pasta)
        self.det_info = QLabel("")
        self.det_info.setTextFormat(Qt.TextFormat.RichText)
        self.det_info.setWordWrap(True)
        v.addWidget(self.det_info)
        v.addStretch(1)
        self.det_b1 = QPushButton("")
        self.det_b1.setObjectName("principal")
        self.det_b1.clicked.connect(lambda: self._acao_detalhe(1))
        v.addWidget(self.det_b1)
        self.det_b2 = QPushButton("")
        self.det_b2.clicked.connect(lambda: self._acao_detalhe(2))
        v.addWidget(self.det_b2)
        self.det_b3 = QPushButton("")
        self.det_b3.clicked.connect(lambda: self._acao_detalhe(3))
        self.det_b3.setVisible(sys.platform == "win32")
        v.addWidget(self.det_b3)
        lay.addWidget(det)
        self._mostrar_detalhes(None)

    def eventFilter(self, obj, ev):
        # Ctrl + roda do mouse muda o tamanho, como no Explorer
        if ev.type() == QEvent.Type.Wheel and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            passo = 16 if ev.angleDelta().y() > 0 else -16
            self.sl_tam.setValue(self.sl_tam.value() + passo)
            return True
        return self._filtro_voltar(obj, ev) or super().eventFilter(obj, ev)

    def _aplicar_visual(self):
        tam = self.sl_tam.value()
        lista = self.grupo_modo.checkedId() == 1
        self.lista.setViewMode(QListView.ViewMode.ListMode if lista else QListView.ViewMode.IconMode)
        self.lista.setMovement(QListView.Movement.Static)
        self.lista.setResizeMode(QListView.ResizeMode.Adjust)
        self.lista.setUniformItemSizes(True)
        if lista:
            icone = max(24, tam // 3)
            self.lista.setWrapping(False)
            self.lista.setWordWrap(False)
            self.lista.setGridSize(QSize())
            self.lista.setSpacing(1)
            self.lista.setIconSize(QSize(icone, icone))
        else:
            self.lista.setWrapping(True)
            self.lista.setWordWrap(True)
            self.lista.setSpacing(0)
            self.lista.setIconSize(QSize(tam, tam))
            self.lista.setGridSize(QSize(max(tam + 30, 110), tam + (68 if tam >= 80 else 60)))
        self.sl_tam.setToolTip(T("Tamanho das miniaturas (Ctrl + roda do mouse)") + f"  ·  {tam} px")
        self.pastas.cfg.setValue("biblioteca_modo", "lista" if lista else "miniaturas")
        self.pastas.cfg.setValue("biblioteca_tamanho", tam)

    # ---- pastas da biblioteca (lista da esquerda) ----
    def raiz_escolhida(self):
        it = self.lista_pastas.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _preencher_pastas(self):
        manter = self._escolher or self.raiz_escolhida()
        self._escolher = None
        self.lista_pastas.blockSignals(True)
        self.lista_pastas.clear()
        if len(self.pastas.lista) > 1:
            it = QListWidgetItem(T("Todas as pastas"))
            it.setData(Qt.ItemDataRole.UserRole, None)
            self.lista_pastas.addItem(it)
        linha = 0
        for p in self.pastas.lista:
            it = QListWidgetItem(os.path.basename(p.rstrip("\\/")) or p)
            it.setToolTip(p)
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.lista_pastas.addItem(it)
            if p == manter:
                linha = self.lista_pastas.count() - 1
        if self.lista_pastas.count():
            self.lista_pastas.setCurrentRow(linha)
        self.lista_pastas.blockSignals(False)
        self.atual = self.raiz_escolhida()

    def _raiz_mudou(self, _linha):
        self.atual = self.raiz_escolhida()
        self.busca.blockSignals(True)
        self.busca.clear()
        self.busca.blockSignals(False)
        self.carregar()

    def _pastas_mudaram(self):
        self._preencher_pastas()
        if self._carregada:
            self.carregar()

    def adicionar_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, T("Adicionar pasta à biblioteca"))
        if pasta:
            self._escolher = os.path.normpath(pasta)
            self.pastas.adicionar(pasta)

    def remover_pasta(self):
        p = self.raiz_escolhida()
        if p:
            self.pastas.remover(p)

    # ---- carregar ----
    def mostrar(self):
        if not self._carregada:
            self._carregada = True
            self.carregar()
        self._mostrar_cache()

    def carregar(self):
        self._mostrar_detalhes(None)
        if not self.pastas.lista:
            self.lista.clear()
            self.pilha.setCurrentIndex(0)
            self.lb_qtd.setText("")
            self.lb_caminho.setText("")
            self.b_voltar.setEnabled(False)
            return
        self.pilha.setCurrentIndex(1)
        n = self._preencher()
        self._atualizar_botao_voltar()
        self.lb_caminho.setText(self._caminho_html())
        extra = " " + T("(limite de {n})", n=num(self.MAX_ARQUIVOS, 0)) if n >= self.MAX_ARQUIVOS else ""
        if self._em_busca or n:
            self.lb_qtd.setText(T("Modelos: {n}", n=num(n, 0)) + extra)
        else:
            self.lb_qtd.setText("")

    def _miniatura_pronta(self, caminho, png):
        self._miniatura_chegou(caminho, png)
        if self.isVisible() and not self.mini._pendentes:
            self._mostrar_cache()
        if self._detalhe and (caminho == self._detalhe[1] or
                              (self._detalhe[0] == "pasta" and self._detalhe[1] in self.pastas_itens
                               and caminho in self.pastas_itens[self._detalhe[1]][1])):
            self._mostrar_detalhes(self.lista.currentItem())

    # ---- cache ----
    def _mostrar_cache(self):
        qtd, total = self.mini.tamanho_cache()
        self.lb_cache.setText(T("Miniaturas em cache: {n} ({mb} MB)", n=num(qtd, 0), mb=num(total / (1024 * 1024), 1))
                              if qtd else T("Cache vazio"))

    def limpar_cache(self):
        qtd, total = self.mini.tamanho_cache()
        if qtd == 0:
            self.lb_cache.setText(T("Cache vazio"))
            return
        r = QMessageBox.question(
            self, T("Limpar cache de miniaturas"),
            T("Apagar as miniaturas salvas ({n} · {mb} MB)?\n\nSeus modelos não serão alterados. As miniaturas serão "
              "geradas de novo quando necessário.", n=num(qtd, 0), mb=num(total / (1024 * 1024), 1)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.mini.limpar_cache()
        finally:
            QApplication.restoreOverrideCursor()

    def _cache_limpo(self):
        if self._carregada:
            self.carregar()
        self._mostrar_cache()

    # ---- detalhes ----
    def _acao_detalhe(self, botao):
        if not self._detalhe:
            return
        tipo, caminho = self._detalhe
        if tipo == "pasta":
            if botao == 1:
                self.entrar(caminho)
            elif botao == 2:
                modelos = modelos_dentro(caminho)
                if modelos and _confirmar_muitos(self, len(modelos)):
                    self.adicionar_pedido.emit(modelos)
            else:
                abrir_no_explorer(caminho)
        else:
            if botao == 1:
                self.abrir_pedido.emit([caminho])
            elif botao == 2:
                self.adicionar_pedido.emit([caminho])
            else:
                mostrar_na_pasta(caminho)

    def _mostrar_detalhes(self, it):
        tipo = it.data(PAPEL_TIPO) if it is not None else None
        caminho = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        if tipo not in ("modelo", "pasta") or not caminho:
            self._detalhe = None
            for b in (self.det_b1, self.det_b2, self.det_b3):
                b.setEnabled(False)
            self.det_b1.setText(T("Abrir"))
            self.det_b2.setText(T("Adicionar à mesa"))
            self.det_b3.setText(T("Mostrar na pasta"))
            self.det_img.setPixmap(QPixmap())
            self.det_img.setText(T("Selecione um modelo\npara ver os detalhes"))
            self.det_nome.setText("")
            self.det_pasta.setText("")
            self.det_info.setText("")
            return
        self._detalhe = (tipo, caminho)
        for b in (self.det_b1, self.det_b2, self.det_b3):
            b.setEnabled(True)
        self.det_nome.setText(os.path.basename(caminho.rstrip("\\/")) or caminho)
        self.det_pasta.setText(os.path.dirname(caminho))
        linhas = []
        if tipo == "pasta":
            self.det_b1.setText(T("Entrar na pasta"))
            self.det_b2.setText(T("Adicionar todos à mesa"))
            self.det_b3.setText(T("Mostrar no Explorer"))
            qtd, exemplos, total, subs = resumo_da_pasta(caminho)
            pngs = []
            for ex in exemplos:
                png = self.mini.caminho_cache(ex)
                pngs.append(png if png and os.path.isfile(png) else None)
            self.det_img.setText("")
            self.det_img.setPixmap(pixmap_pasta(pngs, 246))
            linhas.append(f"<b>{T('Modelos 3D')}:</b> {num(qtd, 0)}")
            linhas.append(f"<b>{T('Subpastas')}:</b> {num(subs, 0)}")
            linhas.append(f"<b>{T('Tamanho total')}:</b> {num(total / (1024 * 1024), 1)} MB")
            self.det_info.setText("<br>".join(linhas))
            return
        self.det_b1.setText(T("Abrir"))
        self.det_b2.setText(T("Adicionar à mesa"))
        self.det_b3.setText(T("Mostrar na pasta"))
        png = self.mini.caminho_cache(caminho)
        if png and os.path.isfile(png):
            self.det_img.setText("")
            self.det_img.setPixmap(QPixmap(png).scaled(246, 246, Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation))
        else:
            self.det_img.setPixmap(QPixmap())
            self.det_img.setText(T("Gerando miniatura…"))
        info = self.mini.info(caminho)
        if info:
            d = info.get("dim", [0, 0, 0])
            linhas.append(f"<b>{T('Dimensões')}:</b> {num(d[0])} × {num(d[1])} × {num(d[2])} mm")
            linhas.append(f"<b>{T('Triângulos')}:</b> {num(info.get('tri', 0), 0)}")
        if caminho.lower().endswith(".zip"):
            try:
                n = len(modelos_no_zip(caminho))
                linhas.append(f"<b>{T('Modelos 3D no arquivo')}:</b> {n}")
            except Exception:
                linhas.append(f"<b>{T('arquivo .zip ilegível')}</b>")
        try:
            st = os.stat(caminho)
            linhas.append(f"<b>{T('Tamanho')}:</b> {num(st.st_size / (1024 * 1024), 2)} MB")
            linhas.append(f"<b>{T('Modificado em')}:</b> {data_hora(st.st_mtime)}")
        except OSError:
            pass
        self.det_info.setText("<br>".join(linhas))


class BibliotecaLateral(QWidget, NavegadorPastas):
    """Aba Biblioteca do painel lateral: escolher pasta e navegar pelas subpastas."""
    abrir_pedido = Signal(list)
    adicionar_pedido = Signal(list)
    MAX_ARQUIVOS = 1500

    def __init__(self, pastas, miniaturas):
        super().__init__()
        self.pastas = pastas
        self.mini = miniaturas
        self._carregada = False

        v = QVBoxLayout(self)
        v.setContentsMargins(4, 10, 4, 4)
        v.setSpacing(8)
        linha = QHBoxLayout()
        self.cmb_pasta = QComboBox()
        self.cmb_pasta.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.cmb_pasta.setMinimumContentsLength(8)
        self.cmb_pasta.currentIndexChanged.connect(self._raiz_mudou)
        linha.addWidget(self.cmb_pasta, 1)
        b = QToolButton()
        b.setText("+")
        b.setObjectName("mais")
        b.setToolTip(T("Adicionar pasta à biblioteca…"))
        b.clicked.connect(self._adicionar_pasta_nova)
        linha.addWidget(b)
        v.addLayout(linha)
        linha = QHBoxLayout()
        self.b_voltar = QToolButton()
        self.b_voltar.setText("←")
        self.b_voltar.setObjectName("navegar")
        self.b_voltar.setToolTip(T("Voltar para a pasta anterior"))
        self.b_voltar.clicked.connect(self.voltar)
        linha.addWidget(self.b_voltar, 0, Qt.AlignmentFlag.AlignTop)
        self.lb_caminho = QLabel("")
        self.lb_caminho.setTextFormat(Qt.TextFormat.RichText)
        self.lb_caminho.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.lb_caminho.setWordWrap(True)
        self.lb_caminho.linkActivated.connect(self._caminho_clicado)
        linha.addWidget(self.lb_caminho, 1)
        v.addLayout(linha)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText(T("Buscar por nome…"))
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(self._busca_mudou)
        v.addWidget(self.busca)
        self.pilha = QStackedWidget()
        vazio = QLabel(T("Nenhuma pasta na biblioteca.\nClique em “+” para adicionar."))
        vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vazio.setObjectName("fraco")
        self.pilha.addWidget(vazio)
        self.lista = QListWidget()
        self.lista.setIconSize(QSize(48, 48))
        self.lista.setUniformItemSizes(True)
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista.itemDoubleClicked.connect(self._duplo_clique)
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu)
        self.pilha.addWidget(self.lista)
        v.addWidget(self.pilha, 1)
        self.lb_qtd = QLabel("")
        self.lb_qtd.setObjectName("fraco")
        v.addWidget(self.lb_qtd)
        dica = QLabel(T("Duplo clique: abrir   ·   Botão direito: mais opções"))
        dica.setObjectName("fraco")
        dica.setWordWrap(True)
        v.addWidget(dica)

        self._iniciar_navegacao()
        self._ligar_atalhos_voltar()
        self.mini.pronta.connect(self._miniatura_chegou)
        self.mini.cache_limpo.connect(lambda: self._carregada and self.carregar())
        self.pastas.mudaram.connect(self._pastas_mudaram)
        self._preencher_combo()

    def raiz_escolhida(self):
        return self.cmb_pasta.currentData()

    def _preencher_combo(self, escolher=None):
        atual = escolher or self.cmb_pasta.currentData()
        self.cmb_pasta.blockSignals(True)
        self.cmb_pasta.clear()
        if len(self.pastas.lista) > 1:
            self.cmb_pasta.addItem(T("Todas as pastas"), None)
        for p in self.pastas.lista:
            self.cmb_pasta.addItem(os.path.basename(p.rstrip("\\/")) or p, p)
            self.cmb_pasta.setItemData(self.cmb_pasta.count() - 1, p, Qt.ItemDataRole.ToolTipRole)
        i = self.cmb_pasta.findData(atual) if atual else -1
        self.cmb_pasta.setCurrentIndex(i if i >= 0 else 0)
        self.cmb_pasta.blockSignals(False)
        self.atual = self.raiz_escolhida()

    def _raiz_mudou(self, _i):
        self.atual = self.raiz_escolhida()
        self.busca.blockSignals(True)
        self.busca.clear()
        self.busca.blockSignals(False)
        self.carregar()

    def _pastas_mudaram(self):
        self._preencher_combo()
        if self._carregada:
            self.carregar()

    def _adicionar_pasta_nova(self):
        pasta = QFileDialog.getExistingDirectory(self, T("Adicionar pasta à biblioteca"))
        if pasta:
            pasta = self.pastas.adicionar(pasta)
            self._preencher_combo(escolher=pasta)
            self.carregar()

    def mostrar(self):
        if not self._carregada:
            self._carregada = True
            self.carregar()

    def carregar(self):
        if not self.pastas.lista:
            self.lista.clear()
            self.pilha.setCurrentIndex(0)
            self.lb_qtd.setText("")
            self.lb_caminho.setText("")
            self.b_voltar.setEnabled(False)
            return
        self.pilha.setCurrentIndex(1)
        n = self._preencher()
        self._atualizar_botao_voltar()
        self.lb_caminho.setText(self._caminho_html())
        self.lb_qtd.setText(T("Modelos: {n}", n=num(n, 0)) if (n or self._em_busca) else "")

    def eventFilter(self, obj, ev):
        return self._filtro_voltar(obj, ev) or super().eventFilter(obj, ev)


# ---------------------------------------------------------------------------
#  Janela principal
# ---------------------------------------------------------------------------
class Janela(QMainWindow):
    PAG_VISUALIZADOR, PAG_BIBLIOTECA = 0, 1

    def __init__(self):
        super().__init__()
        self.cfg = QSettings("VisualizadorSTL", "VisualizadorSTL")
        self.cena = Cena()
        self.setWindowTitle(nome_app())
        self.resize(1360, 840)
        self.setAcceptDrops(True)

        self.visor = Visor(self.cena)
        self.visor.alterado.connect(self._atualizar_painel)
        self.visor.previa_mudou.connect(self._mostrar_medidas)
        self.visor.selecao_mudou.connect(self._atualizar_painel)
        self.visor.menu_pedido.connect(self._menu_contexto)

        self.pastas = Pastas(self.cfg)
        self.miniaturas = Miniaturas(lambda: self.visor.cor)

        # página Visualizador
        lateral = QWidget()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(340)
        v = QVBoxLayout(lateral)
        v.setContentsMargins(12, 12, 12, 8)
        v.setSpacing(10)
        v.addWidget(self._montar_arquivo())
        self.bib_lateral = BibliotecaLateral(self.pastas, self.miniaturas)
        self.bib_lateral.abrir_pedido.connect(lambda c: self.abrir(c, substituir=True, trocar_pagina=False))
        self.bib_lateral.adicionar_pedido.connect(lambda c: self.abrir(c, substituir=False, trocar_pagina=False))
        self.abas = QTabWidget()
        self.abas.addTab(self.bib_lateral, T("Biblioteca"))
        self.abas.addTab(self._rolavel(self._montar_aba_objeto()), T("Objeto"))
        self.abas.addTab(self._rolavel(self._montar_aba_configuracoes()), T("Configurações"))
        self.abas.setCurrentIndex(1)
        self.abas.currentChanged.connect(lambda i: self.bib_lateral.mostrar() if i == 0 else None)
        v.addWidget(self.abas, 1)
        rodape = QLabel(f"<a href='#' style='color:gray;text-decoration:none'>{nome_app()} {VERSAO} · {AUTOR}</a>")
        rodape.setObjectName("fraco")
        rodape.setToolTip(T("Sobre o {nome}", nome=nome_app()))
        rodape.linkActivated.connect(lambda _l: self.mostrar_sobre())
        rodape.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(rodape)
        pag_vis = QWidget()
        lay = QHBoxLayout(pag_vis)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.visor, 1)
        lay.addWidget(lateral)

        # página Biblioteca
        self.biblioteca = Biblioteca(self.pastas, self.miniaturas)
        self.biblioteca.abrir_pedido.connect(lambda c: self.abrir(c, substituir=True))
        self.biblioteca.adicionar_pedido.connect(lambda c: self.abrir(c, substituir=False))

        self.paginas = QStackedWidget()
        self.paginas.addWidget(pag_vis)          # 0 = Visualizador
        self.paginas.addWidget(self.biblioteca)  # 1 = Biblioteca

        topo = QFrame()
        topo.setObjectName("topo")
        lt = QHBoxLayout(topo)
        lt.setContentsMargins(14, 6, 14, 6)
        nome = QLabel(nome_app())
        nome.setObjectName("titulo")
        lt.addWidget(nome)
        lt.addStretch(1)
        self.grupo_paginas = QButtonGroup(self)
        self.botoes_pagina = {}
        for texto, pagina in ((T("Biblioteca"), self.PAG_BIBLIOTECA), (T("Visualizador"), self.PAG_VISUALIZADOR)):
            b = QPushButton(texto)
            b.setCheckable(True)
            b.setMinimumWidth(116)
            b.clicked.connect(lambda _=False, pg=pagina: self._ir_para(pg))
            self.grupo_paginas.addButton(b)
            self.botoes_pagina[pagina] = b
            lt.addWidget(b)
        lt.addStretch(1)
        espaco = QLabel("")
        espaco.setFixedWidth(nome.sizeHint().width())
        lt.addWidget(espaco)
        self.botoes_pagina[self.PAG_VISUALIZADOR].setChecked(True)

        central = QWidget()
        vc = QVBoxLayout(central)
        vc.setContentsMargins(0, 0, 0, 0)
        vc.setSpacing(0)
        vc.addWidget(topo)
        vc.addWidget(self.paginas, 1)
        self.setCentralWidget(central)

        self.statusBar().showMessage(T(
            "Botão esquerdo: orbitar   ·   Botão direito: menu (arrastar: deslocar)   ·   Roda: zoom   ·   "
            "F: ajustar à tela   ·   Ctrl+Z / Ctrl+Y: desfazer / refazer"))

        self._atalho(QKeySequence.StandardKey.Open, self.abrir_dialogo)
        self._atalho(QKeySequence("Ctrl+I"), self.importar_dialogo)
        self._atalho(QKeySequence("Ctrl+E"), self.exportar)
        self._atalho(QKeySequence("F"), self.visor.enquadrar)
        self._atalho(QKeySequence("M"), lambda: self._alternar_ferramenta("mover"))
        self._atalho(QKeySequence("R"), lambda: self._alternar_ferramenta("girar"))
        self._atalho(QKeySequence("S"), lambda: self._alternar_ferramenta("escala"))
        self._atalho(QKeySequence("D"), lambda: self._alternar_ferramenta("medir"))
        self._atalho(QKeySequence("Esc"), lambda: self.visor.definir_ferramenta(None))
        self._atalho([QKeySequence("Ctrl+Z")], self.desfazer)
        self._atalho([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")], self.refazer)
        self._atalho([QKeySequence("Delete")], self.remover_objeto)

        self._carregar_cfg()
        self._atualizar_painel()

    # ---- montagem da tela ----
    def _atalho(self, tecla, funcao):
        a = QAction(self)
        if isinstance(tecla, list):
            a.setShortcuts(tecla)
        else:
            a.setShortcut(tecla)
        a.triggered.connect(funcao)
        self.addAction(a)

    def _no_visualizador(self):
        return self.paginas.currentIndex() == self.PAG_VISUALIZADOR

    def _alternar_ferramenta(self, k):
        if self._no_visualizador():
            self.visor.definir_ferramenta(None if self.visor.ferramenta == k else k)

    def _ir_para(self, pagina):
        self.paginas.setCurrentIndex(pagina)
        self.botoes_pagina[pagina].setChecked(True)
        if pagina == self.PAG_BIBLIOTECA:
            self.biblioteca.mostrar()

    @staticmethod
    def _rolavel(widget):
        r = QScrollArea()
        r.setWidget(widget)
        r.setWidgetResizable(True)
        r.setFrameShape(QFrame.Shape.NoFrame)
        r.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return r

    @staticmethod
    def _spin(minimo, maximo, casas, sufixo, passo=1.0):
        sb = QDoubleSpinBox()
        sb.setRange(minimo, maximo)
        sb.setDecimals(casas)
        sb.setSuffix(sufixo)
        sb.setSingleStep(passo)
        sb.setKeyboardTracking(False)   # só aplica ao apertar Enter ou sair do campo
        sb.setAccelerated(True)
        # sem isso o campo pede espaço para "100000,00 mm" e o painel da direita corta
        sb.setMinimumWidth(64)
        sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return sb

    @staticmethod
    def _rotulo_eixo(texto, i):
        r, g, b = (int(c * 255) for c in CORES_EIXOS[i])
        lb = QLabel(texto)
        lb.setStyleSheet(f"color: rgb({r},{g},{b}); font-weight: bold; font-size: 14px;")
        lb.setFixedWidth(18)
        return lb

    def _montar_arquivo(self):
        caixa = QFrame()
        caixa.setObjectName("cartao")
        v = QVBoxLayout(caixa)
        v.setContentsMargins(12, 10, 12, 12)
        self.lb_nome = QLabel(T("Nenhum arquivo aberto"))
        self.lb_nome.setObjectName("nome")
        self.lb_nome.setWordWrap(True)
        v.addWidget(self.lb_nome)
        grade = QGridLayout()
        b_abrir = QPushButton(T("Abrir…"))
        b_abrir.setObjectName("principal")
        b_abrir.setToolTip(T("Abrir modelos, substituindo os da mesa (Ctrl+O)"))
        b_abrir.clicked.connect(self.abrir_dialogo)
        b_imp = QPushButton(T("Importar…"))
        b_imp.setToolTip(T("Adicionar modelos à mesa, mantendo os atuais (Ctrl+I)"))
        b_imp.clicked.connect(self.importar_dialogo)
        self.b_exportar = QPushButton(T("Exportar STL…"))
        self.b_exportar.setToolTip(T("Salvar os objetos da mesa como STL (Ctrl+E)"))
        self.b_exportar.clicked.connect(self.exportar)
        grade.addWidget(b_abrir, 0, 0)
        grade.addWidget(b_imp, 0, 1)
        grade.addWidget(self.b_exportar, 1, 0, 1, 2)
        v.addLayout(grade)
        self._controles_cena = [self.b_exportar]
        self._controles_objeto = []
        return caixa

    def _montar_aba_objeto(self):
        painel = QWidget()
        v = QVBoxLayout(painel)
        v.setContentsMargins(4, 10, 4, 4)
        v.setSpacing(10)

        g = QGroupBox(T("Objetos na mesa"))
        gv = QVBoxLayout(g)
        self.lista_objetos = QListWidget()
        self.lista_objetos.setFixedHeight(110)
        self.lista_objetos.currentRowChanged.connect(self._mudou_selecao)
        gv.addWidget(self.lista_objetos)
        linha = QHBoxLayout()
        b_rem = QPushButton(T("Remover"))
        b_rem.setToolTip(T("Remover o objeto selecionado (Delete)"))
        b_rem.clicked.connect(self.remover_objeto)
        b_org = QPushButton(T("Organizar"))
        b_org.setToolTip(T("Distribuir os objetos na mesa automaticamente"))
        b_org.clicked.connect(self.organizar)
        linha.addWidget(b_rem)
        linha.addWidget(b_org)
        gv.addLayout(linha)
        self._controles_objeto.append(b_rem)
        self._controles_cena.append(b_org)
        v.addWidget(g)

        g = QGroupBox(T("Posição"))
        grade = QGridLayout(g)
        self.sb_pos = []
        for i in (0, 1):
            grade.addWidget(self._rotulo_eixo("XY"[i], i), 0, i * 2)
            sb = self._spin(-10000, 10000, 2, " mm", 1.0)
            sb.setToolTip(T("Posição do centro do objeto na mesa"))
            sb.valueChanged.connect(lambda val, i=i: self._mudou_posicao(i, val))
            grade.addWidget(sb, 0, i * 2 + 1)
            self.sb_pos.append(sb)
            self._controles_objeto.append(sb)
        b = QPushButton(T("Centralizar na mesa"))
        b.clicked.connect(self._centralizar)
        grade.addWidget(b, 1, 0, 1, 4)
        self._controles_objeto.append(b)
        grade.setColumnStretch(1, 1)
        grade.setColumnStretch(3, 1)
        v.addWidget(g)

        g = QGroupBox(T("Dimensões"))
        grade = QGridLayout(g)
        self.sb_dim = []
        for i in range(3):
            grade.addWidget(self._rotulo_eixo("XYZ"[i], i), i, 0)
            sb = self._spin(0.01, 100000, 2, " mm", 1.0)
            sb.valueChanged.connect(lambda val, i=i: self._mudou_medida(i, val))
            grade.addWidget(sb, i, 1)
            self.sb_dim.append(sb)
            self._controles_objeto.append(sb)
        grade.addWidget(QLabel("%"), 3, 0)
        self.sb_pct = self._spin(0.1, 100000, 1, " %", 5.0)
        self.sb_pct.setToolTip(T("Escala em relação ao tamanho original"))
        self.sb_pct.valueChanged.connect(self._mudou_pct)
        grade.addWidget(self.sb_pct, 3, 1)
        self._controles_objeto.append(self.sb_pct)
        self.cb_prop = QCheckBox(T("Escala uniforme"))
        self.cb_prop.setToolTip(T("Mantém a proporção entre X, Y e Z ao redimensionar"))
        self.cb_prop.setChecked(True)
        self.cb_prop.toggled.connect(self._mudou_proporcao)
        grade.addWidget(self.cb_prop, 4, 0, 1, 2)
        self.lb_escala = QLabel("")
        self.lb_escala.setObjectName("fraco")
        grade.addWidget(self.lb_escala, 5, 0, 1, 2)
        self.lb_aviso = QLabel("")
        self.lb_aviso.setStyleSheet("color: #ff7a7a;")
        self.lb_aviso.setWordWrap(True)
        self.lb_aviso.hide()
        grade.addWidget(self.lb_aviso, 6, 0, 1, 2)
        grade.setColumnStretch(1, 1)
        v.addWidget(g)

        g = QGroupBox(T("Rotação 90°"))
        grade = QGridLayout(g)
        for i in range(3):
            grade.addWidget(self._rotulo_eixo("XYZ"[i], i), i, 0)
            for j, (texto, graus) in enumerate((("↺  −90°", -90), ("↻  +90°", 90))):
                b = QPushButton(texto)
                b.clicked.connect(lambda _=False, e=i, gr=graus: self._girar(e, gr))
                grade.addWidget(b, i, 1 + j)
                self._controles_objeto.append(b)
        dica = QLabel(T("Para rotação livre, use Rotacionar (R) no menu do botão direito."))
        dica.setObjectName("fraco")
        dica.setWordWrap(True)
        grade.addWidget(dica, 3, 0, 1, 3)
        v.addWidget(g)

        b_rest = QPushButton(T("Redefinir transformações"))
        b_rest.setToolTip(T("Restaura tamanho e rotação originais do objeto selecionado"))
        b_rest.clicked.connect(self.redefinir)
        self._controles_objeto.append(b_rest)
        v.addWidget(b_rest)
        v.addStretch(1)
        return painel

    def _montar_aba_configuracoes(self):
        painel = QWidget()
        v = QVBoxLayout(painel)
        v.setContentsMargins(4, 10, 4, 4)
        v.setSpacing(10)

        g = QGroupBox(T("Idioma"))
        gv = QVBoxLayout(g)
        self.cmb_idioma = QComboBox()
        for codigo, nome in idiomas.IDIOMAS.items():
            self.cmb_idioma.addItem(nome, codigo)
        self.cmb_idioma.setCurrentIndex(max(0, self.cmb_idioma.findData(idiomas.atual())))
        self.cmb_idioma.currentIndexChanged.connect(self._mudou_idioma)
        gv.addWidget(self.cmb_idioma)
        v.addWidget(g)

        g = QGroupBox(T("Exibição"))
        grade = QGridLayout(g)
        grade.addWidget(QLabel(T("Modo de renderização")), 0, 0)
        self.cmb_modo = QComboBox()
        self.cmb_modo.addItems([T("Sólido"), T("Wireframe"), T("Sólido + wireframe")])
        self.cmb_modo.currentIndexChanged.connect(self._mudou_modo)
        grade.addWidget(self.cmb_modo, 0, 1)
        grade.addWidget(QLabel(T("Cor do objeto")), 1, 0)
        self.b_cor = QPushButton("")
        self.b_cor.clicked.connect(self._escolher_cor)
        grade.addWidget(self.b_cor, 1, 1)
        self.cb_mesa = QCheckBox(T("Exibir mesa"))
        self.cb_mesa.setChecked(True)
        self.cb_mesa.toggled.connect(self._mudou_mostrar_mesa)
        grade.addWidget(self.cb_mesa, 2, 0, 1, 2)
        grade.setColumnStretch(1, 1)
        v.addWidget(g)

        g = QGroupBox(T("Volume de impressão"))
        grade = QGridLayout(g)
        self.sb_mesa = []
        for i, eixo in enumerate((T("Largura (X)"), T("Profundidade (Y)"), T("Altura (Z)"))):
            grade.addWidget(QLabel(eixo), i, 0)
            sb = self._spin(10, 5000, 0, " mm", 5)
            sb.valueChanged.connect(lambda val, i=i: self._mudou_mesa(i, val))
            grade.addWidget(sb, i, 1)
            self.sb_mesa.append(sb)
        grade.setColumnStretch(1, 1)
        v.addWidget(g)

        g = QGroupBox(T("Fatiador (impressão 3D)"))
        gv = QVBoxLayout(g)
        lin = QHBoxLayout()
        self.cmb_fatiador = QComboBox()
        instalados = fatiadores_instalados()
        for n in FATIADORES_NOMES:
            self.cmb_fatiador.addItem(n + ("" if n in instalados else "  " + T("(não encontrado)")), n)
        nome_f, exe_f = ler_fatiador()
        if nome_f not in FATIADORES_NOMES:
            self.cmb_fatiador.addItem(nome_f, nome_f)
        self.cmb_fatiador.setCurrentIndex(max(0, self.cmb_fatiador.findData(nome_f)))
        self.cmb_fatiador.currentIndexChanged.connect(
            lambda _=0: gravar_fatiador(self.cmb_fatiador.currentData(), ""))
        lin.addWidget(self.cmb_fatiador, 1)
        b = QPushButton(T("Procurar…"))
        b.clicked.connect(self._procurar_fatiador)
        lin.addWidget(b)
        gv.addLayout(lin)
        lb = QLabel(T("Para quem imprime em 3D: o botão direito no modelo (na biblioteca ou na mesa) ganha "
                      "'Abrir no fatiador', que abre o modelo direto no programa escolhido aqui."))
        lb.setObjectName("fraco")
        lb.setWordWrap(True)
        gv.addWidget(lb)
        v.addWidget(g)

        g = QGroupBox("Windows")
        gv = QVBoxLayout(g)
        b = QPushButton(T("Definir como visualizador padrão"))
        b.clicked.connect(self.registrar_padrao)
        gv.addWidget(b)
        lb = QLabel(T("Faz os arquivos .stl, .3mf, .obj e .ply abrirem neste programa com dois cliques."))
        lb.setObjectName("fraco")
        lb.setWordWrap(True)
        gv.addWidget(lb)
        v.addWidget(g)

        g = QGroupBox(T("Sobre"))
        gv = QVBoxLayout(g)
        b = QPushButton(T("Sobre o {nome}…", nome=nome_app()))
        b.clicked.connect(self.mostrar_sobre)
        gv.addWidget(b)
        v.addWidget(g)
        v.addStretch(1)
        return painel

    def _procurar_fatiador(self):
        r = localizar_fatiador(self)
        if r is None:
            return
        nome = r[0]
        if self.cmb_fatiador.findData(nome) < 0:
            self.cmb_fatiador.addItem(nome, nome)
        self.cmb_fatiador.blockSignals(True)
        self.cmb_fatiador.setCurrentIndex(self.cmb_fatiador.findData(nome))
        self.cmb_fatiador.blockSignals(False)

    # ---- janela "Sobre" ----
    def mostrar_sobre(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(T("Sobre o {nome}", nome=nome_app()))
        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 20, 24, 16)
        v.setSpacing(10)
        icone = caminho_recurso("icone.ico")
        if icone and os.path.exists(icone):
            lb_ic = QLabel()
            lb_ic.setPixmap(QIcon(icone).pixmap(72, 72))
            lb_ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(lb_ic)
        titulo = QLabel(f"<b style='font-size:16pt'>{nome_app()}</b><br>{T('Versão {v}', v=VERSAO)}")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(titulo)
        texto = QLabel(
            T("Criado por {autor}", autor=f"<b>{AUTOR}</b>") + "<br><br>"
            + f"<a href='{LINK_GITHUB}'>{T('Código-fonte no GitHub')}</a><br>"
            + f"<a href='{LINK_KOFI}'>{T('Apoie o projeto no Ko-fi')}</a><br><br>"
            + f"<span style='color:gray'>{T('Programa gratuito e de código aberto, sob a licença MIT.')}<br>"
            + f"© 2026 {AUTOR}</span>")
        texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        texto.setTextFormat(Qt.TextFormat.RichText)
        texto.setOpenExternalLinks(True)
        texto.setWordWrap(True)
        v.addWidget(texto)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botoes.rejected.connect(dlg.reject)
        v.addWidget(botoes)
        dlg.setMinimumWidth(340)
        dlg.exec()

    # ---- idioma ----
    def _mudou_idioma(self, _i):
        codigo = self.cmb_idioma.currentData()
        self.cfg.setValue("idioma", codigo)
        anterior = idiomas.atual()
        idiomas.definir(codigo)      # a pergunta já aparece no idioma novo
        caixa = QMessageBox(self)
        caixa.setWindowTitle(T("Idioma"))
        caixa.setText(T("O novo idioma será aplicado quando o programa for reiniciado."))
        b_agora = caixa.addButton(T("Reiniciar agora"), QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton(T("Depois"), QMessageBox.ButtonRole.RejectRole)
        caixa.exec()
        idiomas.definir(anterior)    # o resto da janela continua como está até reiniciar
        if caixa.clickedButton() is b_agora:
            argumentos = [] if getattr(sys, "frozen", False) else [os.path.abspath(sys.argv[0])]
            if QProcess.startDetached(sys.executable, argumentos):
                self.close()
                QApplication.quit()

    # ---- visualizador padrão do Windows ----
    def registrar_padrao(self):
        if sys.platform != "win32":
            QMessageBox.information(self, nome_app(), T("Esta opção só está disponível no Windows."))
            return
        if instalado_pela_loja():
            # na versão da Microsoft Store os formatos já vêm declarados no pacote;
            # o Windows não deixa o programa mexer no registro, então abrimos a tela de padrões
            QMessageBox.information(self, nome_app(), T(
                "Na versão da Microsoft Store, os arquivos .stl, .3mf, .obj e .ply já aparecem no “Abrir com”.\n\n"
                "Para usar o {app} como padrão, na tela que vai abrir procure “{app}” e escolha-o para cada formato.",
                app=nome_app()))
            try:
                os.startfile("ms-settings:defaultapps")
            except Exception:
                pass
            return
        if not getattr(sys, "frozen", False):
            QMessageBox.information(self, nome_app(), T("Esta opção só funciona na versão .exe do programa."))
            return
        import winreg
        exe = sys.executable
        nome_exe = os.path.basename(exe)
        progid = "MeshDeck.modelo"
        raiz = winreg.HKEY_CURRENT_USER
        try:
            def gravar(chave, valor, nome=""):
                with winreg.CreateKey(raiz, chave) as k:
                    winreg.SetValueEx(k, nome, 0, winreg.REG_SZ, valor)
            gravar(rf"Software\Classes\{progid}", T("Modelos 3D"))
            gravar(rf"Software\Classes\{progid}\DefaultIcon", f'"{exe}",0')
            gravar(rf"Software\Classes\{progid}\shell\open\command", f'"{exe}" "%1"')
            gravar(rf"Software\Classes\Applications\{nome_exe}", nome_app(), "FriendlyAppName")
            gravar(rf"Software\Classes\Applications\{nome_exe}\shell\open\command", f'"{exe}" "%1"')
            for ext in FORMATOS:
                with winreg.CreateKey(raiz, rf"Software\Classes\{ext}\OpenWithProgids") as k:
                    winreg.SetValueEx(k, progid, 0, winreg.REG_NONE, b"")
                gravar(rf"Software\Classes\Applications\{nome_exe}\SupportedTypes", "", ext)
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception as ex:
            QMessageBox.critical(self, nome_app(), T("Não foi possível registrar no Windows:") + f"\n{ex}")
            return
        QMessageBox.information(self, nome_app(), T(
            "Pronto! O programa foi registrado no Windows.\n\nNa janela “Abrir com” que vai aparecer, escolha "
            "“{app}” e clique em “Sempre”.\n\nPara os outros formatos (.3mf, .obj, .ply): clique com o botão direito "
            "no arquivo → Abrir com → Escolher outro aplicativo → {app} → Sempre.\n\nSe mudar o programa de pasta, "
            "use esta opção novamente.", app=nome_app()))
        m = self.sel
        alvo = m.caminho if (m is not None and m.caminho.lower().endswith(FORMATOS) and os.path.isfile(m.caminho)) else None
        if alvo:
            try:
                subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", alvo])
            except Exception:
                pass

    # ---- menu do botão direito ----
    def _menu_contexto(self, pos):
        menu = QMenu(self)
        tem, sel = bool(self.cena.pecas), self.sel is not None
        if not tem:
            menu.addAction(T("Abrir…") + "\tCtrl+O", self.abrir_dialogo)
            menu.addAction(T("Importar…") + "\tCtrl+I", self.importar_dialogo)
            menu.exec(pos)
            return

        for chave, texto, tecla in (("mover", T("Mover"), "M"), ("girar", T("Rotacionar"), "R"),
                                    ("escala", T("Escalar"), "S"), ("medir", T("Medir distância"), "D")):
            a = menu.addAction(f"{texto}\t{tecla}")
            a.setCheckable(True)
            a.setChecked(self.visor.ferramenta == chave)
            a.setEnabled(sel or chave == "medir")
            a.triggered.connect(lambda _=False, k=chave: self._alternar_ferramenta(k))
        menu.addSeparator()

        sub = menu.addMenu(T("Rotação 90°"))
        sub.setEnabled(sel)
        for i, eixo in enumerate("XYZ"):
            for graus in (-90, 90):
                sub.addAction(f"{eixo}   {'−' if graus < 0 else '+'}90°",
                              lambda e=i, g=graus: self._girar(e, g))
        a = menu.addAction(T("Centralizar na mesa"), self._centralizar)
        a.setEnabled(sel)
        menu.addAction(T("Organizar automaticamente"), self.organizar)
        a = menu.addAction(T("Remover objeto") + "\tDel", self.remover_objeto)
        a.setEnabled(sel)
        menu.addSeparator()

        a = menu.addAction(T("Desfazer") + "\tCtrl+Z", self.desfazer)
        a.setEnabled(bool(self.cena._desfazer))
        a = menu.addAction(T("Refazer") + "\tCtrl+Y", self.refazer)
        a.setEnabled(bool(self.cena._refazer))
        menu.addSeparator()

        menu.addAction(T("Salvar captura de tela (PNG)…"), self.salvar_captura)
        if sys.platform == "win32":
            menu.addSeparator()
            menu.addAction(T("Abrir no fatiador ({f})", f=ler_fatiador()[0]), self.abrir_mesa_no_fatiador)
        if EXTRAS_MENU_MESA:
            menu.addSeparator()
            _aplicar_extras(EXTRAS_MENU_MESA, self, menu)
        menu.exec(pos)

    def abrir_mesa_no_fatiador(self):
        """Manda as peças da mesa, já posicionadas, para o fatiador (num .3mf temporário)."""
        pecas = list(self.cena.pecas)
        if not pecas:
            return
        import tempfile
        mesa = self.visor.mesa  # os fatiadores contam a mesa a partir do canto, então desloca os objetos
        desloc = np.array([mesa[0] / 2, mesa[1] / 2, 0.0], dtype=np.float32)
        base = os.path.splitext(pecas[0].nome)[0] if len(pecas) == 1 else "mesa"
        base = re.sub(r"[^\w\-]+", "_", base).strip("_") or "modelo"
        pasta = os.path.join(tempfile.gettempdir(), "MeshDeck", "fatiador")
        os.makedirs(pasta, exist_ok=True)
        destino = os.path.join(pasta, f"{base}_{time.strftime('%H%M%S')}.3mf")
        try:
            salvar_3mf(destino, [(m.nome, m.atual + desloc) for m in pecas])
        except Exception as ex:
            QMessageBox.warning(self, nome_app(), T("Não foi possível preparar o arquivo: {e}", e=ex))
            return
        if abrir_no_fatiador(self, [destino]):
            self.statusBar().showMessage(T("Abrindo no {f}…", f=ler_fatiador()[0]), 6000)

    # ---- configurações salvas ----
    def _carregar_cfg(self):
        c = self.cfg
        self.visor.cor = QColor(str(c.value("cor", "#4fc3f7")))
        self.visor.modo = int(c.value("modo", 0, type=int))
        self.visor.mostrar_mesa = bool(c.value("mostrar_mesa", True, type=bool))
        self.visor.mesa = [float(c.value("mesa_x", 225.0, type=float)),
                           float(c.value("mesa_y", 225.0, type=float)),
                           float(c.value("mesa_z", 265.0, type=float))]
        geo = c.value("geometria")
        if geo is not None:
            self.restoreGeometry(geo)

        for w in [self.cmb_modo, self.cb_mesa] + self.sb_mesa:
            w.blockSignals(True)
        self.cmb_modo.setCurrentIndex(self.visor.modo)
        self.cb_mesa.setChecked(self.visor.mostrar_mesa)
        for i, sb in enumerate(self.sb_mesa):
            sb.setValue(self.visor.mesa[i])
        for w in [self.cmb_modo, self.cb_mesa] + self.sb_mesa:
            w.blockSignals(False)
        self._pintar_botao_cor()
        self.visor.enquadrar()

    def closeEvent(self, e):
        self.cfg.setValue("geometria", self.saveGeometry())
        self.miniaturas.parar()
        super().closeEvent(e)

    # ---- abrir / importar ----
    def abrir_dialogo(self):
        pasta = str(self.cfg.value("ultima_pasta", os.path.expanduser("~")))
        caminhos, _ = QFileDialog.getOpenFileNames(self, T("Abrir"), pasta, filtro_arquivos())
        if caminhos:
            self.abrir(caminhos, substituir=True)

    def importar_dialogo(self):
        pasta = str(self.cfg.value("ultima_pasta", os.path.expanduser("~")))
        caminhos, _ = QFileDialog.getOpenFileNames(self, T("Importar para a mesa"), pasta, filtro_arquivos())
        if caminhos:
            self.abrir(caminhos, substituir=False)

    def _escolher_do_zip(self, caminho):
        membros = modelos_no_zip(caminho)
        if not membros:
            QMessageBox.information(self, nome_app(), T("Nenhum modelo 3D encontrado em:\n{c}", c=caminho))
            return []
        if len(membros) == 1:
            return membros
        dlg = QDialog(self)
        dlg.setWindowTitle(T("{arq} — selecionar modelos", arq=os.path.basename(caminho)))
        dlg.resize(480, 440)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(T("Modelos neste arquivo: {n}. Selecione os que deseja abrir:", n=len(membros))))
        lista = QListWidget()
        for m in membros:
            it = QListWidgetItem(m)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            lista.addItem(it)
        v.addWidget(lista, 1)
        linha = QHBoxLayout()
        for texto, estado in ((T("Selecionar todos"), Qt.CheckState.Checked), (T("Limpar seleção"), Qt.CheckState.Unchecked)):
            b = QPushButton(texto)
            b.clicked.connect(lambda _=False, e=estado: [lista.item(i).setCheckState(e) for i in range(lista.count())])
            linha.addWidget(b)
        linha.addStretch(1)
        v.addLayout(linha)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText(T("Abrir"))
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText(T("Cancelar"))
        botoes.accepted.connect(dlg.accept)
        botoes.rejected.connect(dlg.reject)
        v.addWidget(botoes)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return []
        return [lista.item(i).text() for i in range(lista.count())
                if lista.item(i).checkState() == Qt.CheckState.Checked]

    def _carregar(self, caminhos):
        modelos, erros = [], []
        for c in caminhos:
            try:
                if c.lower().endswith(".zip"):
                    membros = self._escolher_do_zip(c)
                    if not membros:
                        continue
                    chave = hashlib.sha1(c.encode("utf-8", "ignore")).hexdigest()[:10]
                    destino = pasta_temporaria(os.path.join("zip", chave))
                    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    try:
                        for membro, alvo in extrair_do_zip(c, membros, destino):
                            try:
                                modelos.append(Modelo(carregar_modelo(alvo), c, os.path.basename(membro)))
                            except Exception as ex:
                                erros.append(f"{os.path.basename(c)} › {membro}: {ex}")
                    finally:
                        QApplication.restoreOverrideCursor()
                else:
                    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    try:
                        modelos.append(Modelo(carregar_modelo(c), c))
                    finally:
                        QApplication.restoreOverrideCursor()
            except Exception as ex:
                erros.append(f"{os.path.basename(c)}: {ex}")
        if erros:
            QMessageBox.warning(self, nome_app(), T("Não foi possível abrir:") + "\n\n" + "\n".join(erros[:12]))
        return modelos

    def abrir(self, caminhos, substituir=True, trocar_pagina=True):
        if isinstance(caminhos, str):
            caminhos = [caminhos]
        modelos = self._carregar(caminhos)
        if not modelos:
            return
        self.cena.registrar()
        if substituir:
            self.cena.pecas = []
            self.cena.selecionada = None
        for m in modelos:
            self.cena.adicionar(m)
        if substituir and len(modelos) > 1:
            self.cena.organizar(self.visor.mesa[0])
        self.cfg.setValue("ultima_pasta", os.path.dirname(caminhos[0]))
        if trocar_pagina:
            self._ir_para(self.PAG_VISUALIZADOR)
        self.visor.atualizar(enquadrar=True)
        self._atualizar_painel()

    def dragEnterEvent(self, e):
        if any(u.toLocalFile().lower().endswith(EXTENSOES_ABRIR) for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        caminhos = [u.toLocalFile() for u in e.mimeData().urls()
                    if u.toLocalFile().lower().endswith(EXTENSOES_ABRIR)]
        if caminhos:
            # mesa vazia: abre; já tem objeto: importa junto
            self.abrir(caminhos, substituir=not self.cena.pecas)

    # ---- exportar ----
    def _sufixo(self, m):
        if m.uniforme and abs(m.S[0] - 1) > 1e-6:
            return f"_{num(m.S[0] * 100, 0)}pct"
        return "_editado"

    def exportar(self):
        pecas = self.cena.pecas
        if not pecas:
            return
        lista = pecas
        if len(pecas) > 1:
            caixa = QMessageBox(self)
            caixa.setWindowTitle(T("Exportar STL"))
            caixa.setText(T("Objetos na mesa: {n}. O que deseja exportar?", n=len(pecas)))
            b_todos = caixa.addButton(T("Todos em um arquivo"), QMessageBox.ButtonRole.AcceptRole)
            b_sel = caixa.addButton(T("Somente o selecionado"), QMessageBox.ButtonRole.AcceptRole)
            caixa.addButton(T("Cancelar"), QMessageBox.ButtonRole.RejectRole)
            caixa.exec()
            if caixa.clickedButton() is b_todos:
                lista = pecas
            elif caixa.clickedButton() is b_sel and self.sel is not None:
                lista = [self.sel]
            else:
                return
        primeira = lista[0]
        pasta = os.path.dirname(primeira.caminho)
        if len(lista) == 1:
            sugestao = os.path.splitext(primeira.nome)[0] + self._sufixo(primeira) + ".stl"
        else:
            sugestao = "mesa_" + time.strftime("%Y%m%d_%H%M") + ".stl"
        caminho, _ = QFileDialog.getSaveFileName(self, T("Exportar STL"), os.path.join(pasta, sugestao),
                                                 f"{T('Arquivos STL')} (*.stl)")
        if not caminho:
            return
        if not caminho.lower().endswith(".stl"):
            caminho += ".stl"
        try:
            salvar_stl(caminho, np.concatenate([m.atual for m in lista]),
                       f"{APP_NOME} - {os.path.splitext(os.path.basename(caminho))[0]}")
        except Exception as ex:
            QMessageBox.critical(self, nome_app(), T("Não foi possível exportar:") + f"\n{ex}")
            return
        self.statusBar().showMessage(T("Exportado: {c}", c=caminho), 8000)

    def salvar_captura(self):
        if not self.cena.pecas:
            return
        img = self.visor.capturar()
        base = os.path.splitext(self.cena.pecas[0].nome)[0] if len(self.cena.pecas) == 1 else "mesa"
        pasta = str(self.cfg.value("pasta_imagens", self.cfg.value("ultima_pasta", os.path.expanduser("~"))))
        caminho, _ = QFileDialog.getSaveFileName(self, T("Salvar captura de tela"), os.path.join(pasta, base + ".png"),
                                                 f"{T('Imagem PNG')} (*.png)")
        if not caminho:
            return
        if not caminho.lower().endswith(".png"):
            caminho += ".png"
        if img.save(caminho, "PNG"):
            self.cfg.setValue("pasta_imagens", os.path.dirname(caminho))
            self.statusBar().showMessage(T("Captura salva: {c}", c=caminho), 8000)
        else:
            QMessageBox.critical(self, nome_app(), T("Não foi possível salvar a captura de tela."))

    # ---- edição ----
    @property
    def sel(self):
        return self.cena.selecionada

    def _refazer_tela(self, enquadrar=False):
        self.visor.atualizar(enquadrar=enquadrar)
        self._atualizar_painel()

    def desfazer(self):
        if self._no_visualizador() and self.visor._arr is None and self.cena.desfazer():
            self._refazer_tela()
            self.statusBar().showMessage(T("Ação desfeita"), 2000)

    def refazer(self):
        if self._no_visualizador() and self.visor._arr is None and self.cena.refazer():
            self._refazer_tela()
            self.statusBar().showMessage(T("Ação refeita"), 2000)

    def remover_objeto(self):
        if not self._no_visualizador() or self.sel is None:
            return
        self.cena.registrar()
        self.cena.remover(self.sel)
        self._refazer_tela()

    def organizar(self):
        if not self.cena.pecas:
            return
        self.cena.registrar()
        self.cena.organizar(self.visor.mesa[0])
        self._refazer_tela(enquadrar=True)

    def _mudou_selecao(self, linha):
        if 0 <= linha < len(self.cena.pecas):
            self.cena.selecionada = self.cena.pecas[linha]
            self.visor.atualizar(manter_medidas=True)
            self._atualizar_campos()

    def _mudou_posicao(self, i, valor):
        m = self.sel
        if m is None:
            return
        centro = (m.mn + m.mx) / 2
        alvo = valor - self.visor.mesa[i] / 2
        pos = m.pos.copy()
        pos[i] += alvo - centro[i]
        self.cena.registrar()
        m.definir(pos=pos)
        self._refazer_tela()

    def _centralizar(self):
        if self.sel is None:
            return
        self.cena.registrar()
        self.sel.definir(pos=np.zeros(2))
        self._refazer_tela()

    def _mudou_medida(self, i, valor):
        m = self.sel
        if m is None or m.dim[i] <= 1e-9:
            return
        fator = valor / m.dim[i]
        S = m.S.copy()
        if self.cb_prop.isChecked():
            S *= fator
        else:
            S[m.eixo_local(i)] *= fator
        self.cena.registrar()
        m.definir(S=S)
        self._refazer_tela()

    def _mudou_pct(self, valor):
        if self.sel is None:
            return
        self.cena.registrar()
        self.sel.definir(S=np.full(3, valor / 100.0))
        self._refazer_tela()

    def _mudou_proporcao(self, sim):
        self.visor.manter_proporcao = sim

    def _girar(self, eixo, graus):
        if self.sel is None:
            return
        self.cena.registrar()
        self.sel.girar(eixo, graus)
        self._refazer_tela()

    def redefinir(self):
        if self.sel is None:
            return
        self.cena.registrar()
        pos = self.sel.pos.copy()
        self.sel.restaurar()
        self.sel.definir(pos=pos)
        self._refazer_tela()

    # ---- exibição ----
    def _mudou_modo(self, i):
        self.visor.modo = i
        self.cfg.setValue("modo", i)
        self.visor.update()

    def _mudou_mostrar_mesa(self, sim):
        self.visor.mostrar_mesa = sim
        self.cfg.setValue("mostrar_mesa", sim)
        self.visor.update()
        self._atualizar_campos()

    def _escolher_cor(self):
        cor = QColorDialog.getColor(self.visor.cor, self, T("Cor do objeto"))
        if cor.isValid():
            self.visor.cor = cor
            self.cfg.setValue("cor", cor.name())
            self._pintar_botao_cor()
            self.visor.update()

    def _pintar_botao_cor(self):
        c = self.visor.cor
        texto = "#000" if c.lightness() > 140 else "#fff"
        self.b_cor.setText(c.name().upper())
        self.b_cor.setStyleSheet(f"background:{c.name()}; color:{texto}; border:1px solid #555;")

    def _mudou_mesa(self, i, valor):
        self.visor.mesa[i] = valor
        self.cfg.setValue(("mesa_x", "mesa_y", "mesa_z")[i], valor)
        self.visor.update()
        self._atualizar_campos()

    # ---- atualizar campos ----
    def _mostrar_medidas(self, dim):
        for i, sb in enumerate(self.sb_dim):
            sb.blockSignals(True)
            sb.setValue(float(dim[i]))
            sb.blockSignals(False)

    def _atualizar_painel(self):
        self.lista_objetos.blockSignals(True)
        self.lista_objetos.clear()
        for i, m in enumerate(self.cena.pecas):
            self.lista_objetos.addItem(m.nome)
            if m is self.sel:
                self.lista_objetos.setCurrentRow(i)
        self.lista_objetos.blockSignals(False)
        self._atualizar_campos()

    def _atualizar_campos(self):
        pecas, m = self.cena.pecas, self.sel
        for w in self._controles_cena:
            w.setEnabled(bool(pecas))
        for w in self._controles_objeto:
            w.setEnabled(m is not None)
        if not pecas:
            self.lb_nome.setText(T("Nenhum arquivo aberto"))
            self.setWindowTitle(nome_app())
        elif len(pecas) == 1:
            self.lb_nome.setText(pecas[0].nome)
            self.setWindowTitle(f"{pecas[0].nome} — {nome_app()}")
        else:
            self.lb_nome.setText(T("Objetos na mesa: {n}", n=len(pecas)))
            self.setWindowTitle(f"{T('Objetos: {n}', n=len(pecas))} — {nome_app()}")
        self.lb_nome.setToolTip(m.caminho if m is not None else "")
        if m is None:
            self.lb_escala.setText("")
            self.lb_aviso.hide()
            return
        self._mostrar_medidas(m.dim)
        centro = (m.mn + m.mx) / 2
        for i, sb in enumerate(self.sb_pos):
            sb.blockSignals(True)
            sb.setValue(float(centro[i] + self.visor.mesa[i] / 2))
            sb.blockSignals(False)
        esc = m.escala_mundo() * 100
        self.sb_pct.blockSignals(True)
        self.sb_pct.setValue(float(esc.max()))
        self.sb_pct.blockSignals(False)
        if m.uniforme:
            self.lb_escala.setText(T("Escala uniforme: {p}%", p=num(esc[0])))
        else:
            self.lb_escala.setText(T("Escala:  X {x}%  ·  Y {y}%  ·  Z {z}%", x=num(esc[0]), y=num(esc[1]), z=num(esc[2])))
        fora = self.visor.mostrar_mesa and any(self.visor.fora_da_mesa(p.mn, p.mx) for p in pecas)
        self.lb_aviso.setText(T("⚠ Objeto fora da área de impressão") if len(pecas) == 1
                              else T("⚠ Há objetos fora da área de impressão"))
        self.lb_aviso.setVisible(fora)


# ---------------------------------------------------------------------------
#  Tema escuro
# ---------------------------------------------------------------------------
def aplicar_tema(app):
    app.setStyle("Fusion")
    p = QPalette()
    cores = {
        QPalette.ColorRole.Window: "#1f2124", QPalette.ColorRole.WindowText: "#e6e6e6",
        QPalette.ColorRole.Base: "#15171a", QPalette.ColorRole.AlternateBase: "#24272b",
        QPalette.ColorRole.Text: "#e6e6e6", QPalette.ColorRole.Button: "#2c2f34",
        QPalette.ColorRole.ButtonText: "#e6e6e6", QPalette.ColorRole.Highlight: COR_DESTAQUE,
        QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.ToolTipBase: "#2c2f34",
        QPalette.ColorRole.ToolTipText: "#e6e6e6", QPalette.ColorRole.PlaceholderText: "#777777",
    }
    for papel, cor in cores.items():
        p.setColor(papel, QColor(cor))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#666"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#666"))
    app.setPalette(p)
    app.setStyleSheet(f"""
        QWidget {{ font-size: 13px; }}
        QFrame#topo {{ background: #17191c; border-bottom: 1px solid #33363b; }}
        QFrame#topo QPushButton {{ background: transparent; border: 1px solid #3c4046; border-radius: 8px; padding: 6px 14px; }}
        QFrame#topo QPushButton:checked {{ background: {COR_DESTAQUE}; color: white; border-color: {COR_DESTAQUE}; font-weight: bold; }}
        QLabel#titulo {{ color: {COR_DESTAQUE}; font-weight: bold; font-size: 14px; }}
        QWidget#lateral {{ background: #1f2124; border-left: 1px solid #33363b; }}
        QFrame#cartao {{ background: #26292d; border: 1px solid #33363b; border-radius: 10px; }}
        QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
        QTabWidget::pane {{ border: none; }}
        QTabBar::tab {{ background: #26292d; color: #b5bac1; padding: 8px 18px; margin-right: 4px;
                        border-top-left-radius: 8px; border-top-right-radius: 8px; }}
        QTabBar::tab:selected {{ background: {COR_DESTAQUE}; color: white; font-weight: bold; }}
        QTabBar::tab:hover:!selected {{ color: white; }}
        QGroupBox {{ border: 1px solid #33363b; border-radius: 10px; margin-top: 14px;
                     padding: 12px 8px 8px 8px; background: #23262a; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {COR_DESTAQUE}; font-weight: bold; }}
        QPushButton {{ background: #2c2f34; border: 1px solid #3c4046; border-radius: 6px; padding: 6px 10px; }}
        QPushButton:hover {{ border-color: {COR_DESTAQUE}; }}
        QPushButton:pressed {{ background: #24272b; }}
        QPushButton:disabled {{ color: #666; border-color: #2c2f34; }}
        QPushButton#principal {{ background: {COR_DESTAQUE}; color: white; border: none; font-weight: bold; }}
        QPushButton#principal:hover {{ background: #00c4ae; }}
        QDoubleSpinBox, QComboBox, QLineEdit {{ background: #15171a; border: 1px solid #3c4046; border-radius: 5px; padding: 4px 6px; }}
        QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {{ border-color: {COR_DESTAQUE}; }}
        QListWidget {{ background: #15171a; border: 1px solid #33363b; border-radius: 8px; padding: 4px; }}
        QListWidget::item {{ border-radius: 6px; padding: 3px; }}
        QListWidget::item:selected {{ background: rgba(0,174,155,110); color: white; }}
        QListWidget::item:hover:!selected {{ background: #24272b; }}
        QListWidget#grade {{ background: #1a1c1f; }}
        QLabel#nome {{ font-weight: bold; font-size: 14px; }}
        QLabel#fraco {{ color: #8a8f96; font-size: 12px; }}
        QLabel#bolha {{ background: rgba(20,22,25,225); color: white; border: 1px solid {COR_DESTAQUE};
                        border-radius: 6px; padding: 5px 10px; font-weight: bold; }}
        QFrame#barra3d {{ background: rgba(31,33,36,215); border: 1px solid #3c4046; border-radius: 10px; }}
        QFrame#barra3d QToolButton {{ background: transparent; color: #e6e6e6; border: 1px solid transparent;
                                      border-radius: 7px; padding: 4px 8px; font-size: 12px; }}
        QFrame#barra3d QToolButton:hover {{ border-color: {COR_DESTAQUE}; }}
        QFrame#barra3d QToolButton:checked {{ background: {COR_DESTAQUE}; color: white; font-weight: bold; }}
        QMenu {{ background: #26292d; border: 1px solid #3c4046; padding: 4px; }}
        QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
        QMenu::item:selected {{ background: {COR_DESTAQUE}; color: white; }}
        QLabel#pilula {{ background: {COR_DESTAQUE}; color: white; border-radius: 8px; padding: 6px 12px; font-weight: bold; }}
        QFrame#divisoria {{ background: #33363b; max-height: 1px; min-height: 1px; margin: 4px 0; }}
        QToolButton#navegar {{ background: #2c2f34; border: 1px solid #3c4046; border-radius: 6px;
                               font-size: 15px; font-weight: bold; min-width: 30px; min-height: 26px; }}
        QToolButton#navegar:hover {{ border-color: {COR_DESTAQUE}; }}
        QToolButton#navegar:disabled {{ color: #555; }}
        QToolButton#segmento_esq, QToolButton#segmento_dir {{ background: #2c2f34; border: 1px solid #3c4046;
                                  padding: 4px 12px; }}
        QToolButton#segmento_esq {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}
        QToolButton#segmento_dir {{ border-top-right-radius: 6px; border-bottom-right-radius: 6px; border-left: none; }}
        QToolButton#segmento_esq:checked, QToolButton#segmento_dir:checked {{ background: {COR_DESTAQUE}; color: white;
                                  border-color: {COR_DESTAQUE}; font-weight: bold; }}
        QSlider::groove:horizontal {{ height: 4px; background: #3c4046; border-radius: 2px; }}
        QSlider::sub-page:horizontal {{ background: {COR_DESTAQUE}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ background: white; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
        QLabel#previa {{ background: #16181b; border: 1px solid #33363b; border-radius: 8px; color: #8a8f96; }}
        QToolButton#mais {{ background: {COR_DESTAQUE}; color: white; border: none; border-radius: 5px;
                            font-weight: bold; font-size: 16px; min-width: 28px; min-height: 26px; }}
        QComboBox QAbstractItemView {{ background: #26292d; selection-background-color: {COR_DESTAQUE}; }}
        QMenu::separator {{ height: 1px; background: #3c4046; margin: 4px 8px; }}
        QMenu::item:disabled {{ color: #666; }}
        QStatusBar {{ background: #17191c; color: #9aa0a6; }}
    """)


# ---------------------------------------------------------------------------
#  Registro de erros (para descobrir problemas sem ver o console)
# ---------------------------------------------------------------------------
def instalado_pela_loja():
    """True quando o programa roda como pacote MSIX (versão da Microsoft Store)."""
    if sys.platform != "win32":
        return False
    try:
        tamanho = ctypes.c_uint32(0)
        # 15700 = APPMODEL_ERROR_NO_PACKAGE (programa comum, fora da loja)
        return ctypes.windll.kernel32.GetCurrentPackageFullName(ctypes.byref(tamanho), None) != 15700
    except Exception:
        return False


def _registrar_erro(texto):
    """Anota um problema no erros.log sem interromper o programa."""
    try:
        with open(os.path.join(pasta_dados(), "erros.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + texto + "\n")
    except Exception:
        pass


def _gancho_erros(tipo, valor, tb):
    texto = "".join(traceback.format_exception(tipo, valor, tb))
    try:
        with open(os.path.join(pasta_dados(), "erros.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + texto + "\n")
    except Exception:
        pass
    try:
        QMessageBox.critical(None, nome_app(), f"{T('Aconteceu um erro inesperado:')}\n\n{valor}\n\n"
                                             f"{T('Detalhes salvos em:')}\n{os.path.join(pasta_dados(), 'erros.log')}")
    except Exception:
        pass


def _limpar_temporarios():
    import tempfile
    for sub in ("zip", "miniaturas"):
        shutil.rmtree(os.path.join(tempfile.gettempdir(), "VisualizadorSTL", sub), ignore_errors=True)


def main():
    sys.excepthook = _gancho_erros
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DarkDragonal.MeshDeck")
        except Exception:
            pass
    _limpar_temporarios()

    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NOME)
    # idioma: o escolhido em Configurações, ou o do Windows na primeira vez
    cfg = QSettings("VisualizadorSTL", "VisualizadorSTL")
    codigo = str(cfg.value("idioma", "")) or idiomas.detectar(QLocale.system().name())
    idiomas.definir(codigo)
    QLocale.setDefault(QLocale(idiomas.LOCALES_QT[idiomas.atual()]))
    aplicar_tema(app)
    icone = caminho_recurso("icone.ico")
    if os.path.isfile(icone):
        app.setWindowIcon(QIcon(icone))

    janela = Janela()
    janela.show()

    arquivos = [a for a in sys.argv[1:] if os.path.isfile(a)]
    if arquivos:
        QTimer.singleShot(50, lambda: janela.abrir(arquivos, substituir=True))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
