# -*- coding: utf-8 -*-
"""
Traduções do MeshDeck.

Como funciona: a chave é o texto em português; para cada chave há a tradução
nos outros idiomas. Se faltar uma tradução, o programa mostra o texto em português.
Para adicionar um idioma: inclua o código em IDIOMAS e a tradução em cada item de TEXTOS.
"""

IDIOMAS = {
    "pt": "Português (Brasil)",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "ja": "日本語",
}

# separador decimal e de milhar de cada idioma
SEPARADORES = {"pt": (",", "."), "en": (".", ","), "es": (",", "."), "fr": (",", " "),
               "de": (",", "."), "it": (",", "."), "ja": (".", ",")}
FORMATO_DATA = {"pt": "%d/%m/%Y %H:%M", "en": "%m/%d/%Y %I:%M %p", "es": "%d/%m/%Y %H:%M",
                "fr": "%d/%m/%Y %H:%M", "de": "%d.%m.%Y %H:%M", "it": "%d/%m/%Y %H:%M", "ja": "%Y/%m/%d %H:%M"}
LOCALES_QT = {"pt": "pt_BR", "en": "en_US", "es": "es_ES", "fr": "fr_FR", "de": "de_DE", "it": "it_IT", "ja": "ja_JP"}

_atual = "pt"


def definir(codigo):
    global _atual
    _atual = codigo if codigo in IDIOMAS else "en"


def atual():
    return _atual


def detectar(nome_locale):
    """'pt_BR' -> 'pt'; idioma sem tradução -> 'en'."""
    codigo = (nome_locale or "").split("_")[0].split("-")[0].lower()
    return codigo if codigo in IDIOMAS else "en"


def T(texto, **valores):
    """Traduz o texto (em português) para o idioma atual e preenche os {campos}."""
    if _atual != "pt":
        texto = TEXTOS.get(texto, {}).get(_atual, texto)
    return texto.format(**valores) if valores else texto


#  en / es / fr / de / it / ja
TEXTOS = {
    # ---- sobre ----
    "Sobre": {"en": "About", "es": "Acerca de", "fr": "À propos", "de": "Über", "it": "Informazioni", "ja": "情報"},
    "Sobre o {nome}…": {"en": "About {nome}…", "es": "Acerca de {nome}…", "fr": "À propos de {nome}…",
                        "de": "Über {nome}…", "it": "Informazioni su {nome}…", "ja": "{nome} について…"},
    "Sobre o {nome}": {"en": "About {nome}", "es": "Acerca de {nome}", "fr": "À propos de {nome}",
                       "de": "Über {nome}", "it": "Informazioni su {nome}", "ja": "{nome} について"},
    "Versão {v}": {"en": "Version {v}", "es": "Versión {v}", "fr": "Version {v}", "de": "Version {v}",
                   "it": "Versione {v}", "ja": "バージョン {v}"},
    "Criado por {autor}": {"en": "Created by {autor}", "es": "Creado por {autor}", "fr": "Créé par {autor}",
                           "de": "Erstellt von {autor}", "it": "Creato da {autor}", "ja": "作成者: {autor}"},
    "Código-fonte no GitHub": {"en": "Source code on GitHub", "es": "Código fuente en GitHub",
                               "fr": "Code source sur GitHub", "de": "Quellcode auf GitHub",
                               "it": "Codice sorgente su GitHub", "ja": "GitHub のソースコード"},
    "Apoie o projeto no Ko-fi": {"en": "Support the project on Ko-fi", "es": "Apoya el proyecto en Ko-fi",
                                 "fr": "Soutenez le projet sur Ko-fi", "de": "Unterstütze das Projekt auf Ko-fi",
                                 "it": "Sostieni il progetto su Ko-fi", "ja": "Ko-fi でプロジェクトを支援"},
    "Programa gratuito e de código aberto, sob a licença MIT.": {
        "en": "Free and open-source software, under the MIT license.",
        "es": "Programa gratuito y de código abierto, bajo la licencia MIT.",
        "fr": "Logiciel gratuit et open source, sous licence MIT.",
        "de": "Kostenlose Open-Source-Software unter der MIT-Lizenz.",
        "it": "Programma gratuito e open source, con licenza MIT.",
        "ja": "MIT ライセンスの無料オープンソースソフトウェアです。"},
    # ---- programa e páginas ----
    "Visualizador": {
        "en": "Viewer", "es": "Visor", "fr": "Visionneuse", "de": "Ansicht", "it": "Visualizzatore", "ja": "ビューア"},
    "Biblioteca": {
        "en": "Library", "es": "Biblioteca", "fr": "Bibliothèque", "de": "Bibliothek", "it": "Libreria", "ja": "ライブラリ"},
    "Objeto": {
        "en": "Object", "es": "Objeto", "fr": "Objet", "de": "Objekt", "it": "Oggetto", "ja": "オブジェクト"},
    "Configurações": {
        "en": "Settings", "es": "Configuración", "fr": "Paramètres", "de": "Einstellungen", "it": "Impostazioni", "ja": "設定"},

    # ---- ferramentas e vistas ----
    "Mover": {"en": "Move", "es": "Mover", "fr": "Déplacer", "de": "Verschieben", "it": "Sposta", "ja": "移動"},
    "Rotacionar": {"en": "Rotate", "es": "Rotar", "fr": "Pivoter", "de": "Drehen", "it": "Ruota", "ja": "回転"},
    "Escalar": {"en": "Scale", "es": "Escalar", "fr": "Redimensionner", "de": "Skalieren", "it": "Scala", "ja": "拡大縮小"},
    "Medir distância": {
        "en": "Measure distance", "es": "Medir distancia", "fr": "Mesurer la distance",
        "de": "Abstand messen", "it": "Misura distanza", "ja": "距離を測定"},
    "{ferramenta}   ·   Esc para sair": {
        "en": "{ferramenta}   ·   Esc to exit", "es": "{ferramenta}   ·   Esc para salir",
        "fr": "{ferramenta}   ·   Échap pour quitter", "de": "{ferramenta}   ·   Esc zum Beenden",
        "it": "{ferramenta}   ·   Esc per uscire", "ja": "{ferramenta}   ·   Escで終了"},
    "Arraste um modelo 3D para cá\n(.stl  .3mf  .obj  .ply  .zip)\nou use  “Abrir…”": {
        "en": "Drag a 3D model here\n(.stl  .3mf  .obj  .ply  .zip)\nor use  “Open…”",
        "es": "Arrastra un modelo 3D aquí\n(.stl  .3mf  .obj  .ply  .zip)\no usa  “Abrir…”",
        "fr": "Glissez un modèle 3D ici\n(.stl  .3mf  .obj  .ply  .zip)\nou utilisez  « Ouvrir… »",
        "de": "3D-Modell hierher ziehen\n(.stl  .3mf  .obj  .ply  .zip)\noder  „Öffnen…“ verwenden",
        "it": "Trascina qui un modello 3D\n(.stl  .3mf  .obj  .ply  .zip)\noppure usa  “Apri…”",
        "ja": "ここに3Dモデルをドラッグ\n(.stl  .3mf  .obj  .ply  .zip)\nまたは「開く…」を使用"},
    "Iso": {"en": "Iso", "es": "Iso", "fr": "Iso", "de": "Iso", "it": "Iso", "ja": "等角"},
    "Frente": {"en": "Front", "es": "Frente", "fr": "Face", "de": "Vorne", "it": "Fronte", "ja": "正面"},
    "Topo": {"en": "Top", "es": "Superior", "fr": "Dessus", "de": "Oben", "it": "Alto", "ja": "上面"},
    "Lado": {"en": "Side", "es": "Lateral", "fr": "Côté", "de": "Seite", "it": "Lato", "ja": "側面"},
    "Trás": {"en": "Back", "es": "Atrás", "fr": "Arrière", "de": "Hinten", "it": "Retro", "ja": "背面"},
    "Vista isométrica": {"en": "Isometric view", "es": "Vista isométrica", "fr": "Vue isométrique",
                         "de": "Isometrische Ansicht", "it": "Vista isometrica", "ja": "等角ビュー"},
    "Vista frontal": {"en": "Front view", "es": "Vista frontal", "fr": "Vue de face",
                      "de": "Vorderansicht", "it": "Vista frontale", "ja": "正面ビュー"},
    "Vista superior": {"en": "Top view", "es": "Vista superior", "fr": "Vue de dessus",
                       "de": "Draufsicht", "it": "Vista dall'alto", "ja": "上面ビュー"},
    "Vista lateral": {"en": "Side view", "es": "Vista lateral", "fr": "Vue de côté",
                      "de": "Seitenansicht", "it": "Vista laterale", "ja": "側面ビュー"},
    "Vista traseira": {"en": "Back view", "es": "Vista trasera", "fr": "Vue arrière",
                       "de": "Rückansicht", "it": "Vista posteriore", "ja": "背面ビュー"},
    "Ajustar à tela (F ou duplo clique)": {
        "en": "Fit to screen (F or double-click)", "es": "Ajustar a la pantalla (F o doble clic)",
        "fr": "Ajuster à l'écran (F ou double-clic)", "de": "An Bildschirm anpassen (F oder Doppelklick)",
        "it": "Adatta allo schermo (F o doppio clic)", "ja": "画面に合わせる (F またはダブルクリック)"},
    "Distância: {d} mm     ΔX {x}  ·  ΔY {y}  ·  ΔZ {z} mm": {
        "en": "Distance: {d} mm     ΔX {x}  ·  ΔY {y}  ·  ΔZ {z} mm",
        "es": "Distancia: {d} mm     ΔX {x}  ·  ΔY {y}  ·  ΔZ {z} mm",
        "fr": "Distance : {d} mm     ΔX {x}  ·  ΔY {y}  ·  ΔZ {z} mm",
        "de": "Abstand: {d} mm     ΔX {x}  ·  ΔY {y}  ·  ΔZ {z} mm",
        "it": "Distanza: {d} mm     ΔX {x}  ·  ΔY {y}  ·  ΔZ {z} mm",
        "ja": "距離: {d} mm     ΔX {x}  ·  ΔY {y}  ·  ΔZ {z} mm"},
    "Selecione o primeiro ponto no objeto": {
        "en": "Select the first point on the object", "es": "Selecciona el primer punto en el objeto",
        "fr": "Sélectionnez le premier point sur l'objet", "de": "Ersten Punkt auf dem Objekt wählen",
        "it": "Seleziona il primo punto sull'oggetto", "ja": "オブジェクト上の最初の点を選択"},
    "Selecione o segundo ponto": {
        "en": "Select the second point", "es": "Selecciona el segundo punto", "fr": "Sélectionnez le second point",
        "de": "Zweiten Punkt wählen", "it": "Seleziona il secondo punto", "ja": "2番目の点を選択"},

    # ---- barra de status ----
    "Botão esquerdo: orbitar   ·   Botão direito: menu (arrastar: deslocar)   ·   Roda: zoom   ·   "
    "F: ajustar à tela   ·   Ctrl+Z / Ctrl+Y: desfazer / refazer": {
        "en": "Left button: orbit   ·   Right button: menu (drag: pan)   ·   Wheel: zoom   ·   "
              "F: fit to screen   ·   Ctrl+Z / Ctrl+Y: undo / redo",
        "es": "Botón izquierdo: orbitar   ·   Botón derecho: menú (arrastrar: desplazar)   ·   Rueda: zoom   ·   "
              "F: ajustar a la pantalla   ·   Ctrl+Z / Ctrl+Y: deshacer / rehacer",
        "fr": "Bouton gauche : orbite   ·   Bouton droit : menu (glisser : déplacer la vue)   ·   Molette : zoom   ·   "
              "F : ajuster à l'écran   ·   Ctrl+Z / Ctrl+Y : annuler / rétablir",
        "de": "Linke Taste: Orbit   ·   Rechte Taste: Menü (Ziehen: Verschieben)   ·   Mausrad: Zoom   ·   "
              "F: an Bildschirm anpassen   ·   Strg+Z / Strg+Y: Rückgängig / Wiederholen",
        "it": "Tasto sinistro: orbita   ·   Tasto destro: menu (trascina: sposta vista)   ·   Rotella: zoom   ·   "
              "F: adatta allo schermo   ·   Ctrl+Z / Ctrl+Y: annulla / ripeti",
        "ja": "左ボタン: 回転   ·   右ボタン: メニュー (ドラッグ: パン)   ·   ホイール: ズーム   ·   "
              "F: 画面に合わせる   ·   Ctrl+Z / Ctrl+Y: 元に戻す / やり直し"},

    # ---- arquivo ----
    "Nenhum arquivo aberto": {
        "en": "No file open", "es": "Ningún archivo abierto", "fr": "Aucun fichier ouvert",
        "de": "Keine Datei geöffnet", "it": "Nessun file aperto", "ja": "ファイルが開かれていません"},
    "Abrir": {"en": "Open", "es": "Abrir", "fr": "Ouvrir", "de": "Öffnen", "it": "Apri", "ja": "開く"},
    "Abrir…": {"en": "Open…", "es": "Abrir…", "fr": "Ouvrir…", "de": "Öffnen…", "it": "Apri…", "ja": "開く…"},
    "Importar…": {"en": "Import…", "es": "Importar…", "fr": "Importer…", "de": "Importieren…", "it": "Importa…",
                  "ja": "インポート…"},
    "Exportar STL…": {"en": "Export STL…", "es": "Exportar STL…", "fr": "Exporter en STL…", "de": "STL exportieren…",
                      "it": "Esporta STL…", "ja": "STLをエクスポート…"},
    "Exportar STL": {"en": "Export STL", "es": "Exportar STL", "fr": "Exporter en STL", "de": "STL exportieren",
                     "it": "Esporta STL", "ja": "STLをエクスポート"},
    "Abrir modelos, substituindo os da mesa (Ctrl+O)": {
        "en": "Open models, replacing those on the bed (Ctrl+O)",
        "es": "Abrir modelos, reemplazando los de la cama (Ctrl+O)",
        "fr": "Ouvrir des modèles en remplaçant ceux du plateau (Ctrl+O)",
        "de": "Modelle öffnen und die auf dem Druckbett ersetzen (Strg+O)",
        "it": "Apri modelli, sostituendo quelli sul piatto (Ctrl+O)",
        "ja": "モデルを開く (ベッド上のモデルを置き換え) (Ctrl+O)"},
    "Adicionar modelos à mesa, mantendo os atuais (Ctrl+I)": {
        "en": "Add models to the bed, keeping the current ones (Ctrl+I)",
        "es": "Añadir modelos a la cama, manteniendo los actuales (Ctrl+I)",
        "fr": "Ajouter des modèles au plateau en gardant les actuels (Ctrl+I)",
        "de": "Modelle zum Druckbett hinzufügen, vorhandene bleiben (Strg+I)",
        "it": "Aggiungi modelli al piatto mantenendo quelli attuali (Ctrl+I)",
        "ja": "現在のモデルを残したままベッドに追加 (Ctrl+I)"},
    "Salvar os objetos da mesa como STL (Ctrl+E)": {
        "en": "Save the objects on the bed as STL (Ctrl+E)", "es": "Guardar los objetos de la cama como STL (Ctrl+E)",
        "fr": "Enregistrer les objets du plateau en STL (Ctrl+E)", "de": "Objekte auf dem Druckbett als STL speichern (Strg+E)",
        "it": "Salva gli oggetti sul piatto come STL (Ctrl+E)", "ja": "ベッド上のオブジェクトをSTLとして保存 (Ctrl+E)"},
    "Importar para a mesa": {
        "en": "Import to bed", "es": "Importar a la cama", "fr": "Importer sur le plateau", "de": "Zum Druckbett importieren",
        "it": "Importa sul piatto", "ja": "ベッドにインポート"},
    "Modelos 3D": {"en": "3D models", "es": "Modelos 3D", "fr": "Modèles 3D", "de": "3D-Modelle", "it": "Modelli 3D",
                   "ja": "3Dモデル"},
    "Todos os arquivos": {"en": "All files", "es": "Todos los archivos", "fr": "Tous les fichiers", "de": "Alle Dateien",
                          "it": "Tutti i file", "ja": "すべてのファイル"},
    "Arquivos STL": {"en": "STL files", "es": "Archivos STL", "fr": "Fichiers STL", "de": "STL-Dateien",
                     "it": "File STL", "ja": "STLファイル"},
    "Imagem PNG": {"en": "PNG image", "es": "Imagen PNG", "fr": "Image PNG", "de": "PNG-Bild", "it": "Immagine PNG",
                   "ja": "PNG画像"},
    "Programas": {"en": "Programs", "es": "Programas", "fr": "Programmes", "de": "Programme", "it": "Programmi",
                  "ja": "プログラム"},

    # ---- aba Objeto ----
    "Objetos na mesa": {
        "en": "Objects on bed", "es": "Objetos en la cama", "fr": "Objets sur le plateau", "de": "Objekte auf dem Druckbett",
        "it": "Oggetti sul piatto", "ja": "ベッド上のオブジェクト"},
    "Remover": {"en": "Remove", "es": "Quitar", "fr": "Retirer", "de": "Entfernen", "it": "Rimuovi", "ja": "削除"},
    "Remover o objeto selecionado (Delete)": {
        "en": "Remove the selected object (Delete)", "es": "Quitar el objeto seleccionado (Supr)",
        "fr": "Retirer l'objet sélectionné (Suppr)", "de": "Ausgewähltes Objekt entfernen (Entf)",
        "it": "Rimuovi l'oggetto selezionato (Canc)", "ja": "選択したオブジェクトを削除 (Delete)"},
    "Organizar": {"en": "Arrange", "es": "Organizar", "fr": "Organiser", "de": "Anordnen", "it": "Disponi", "ja": "整列"},
    "Distribuir os objetos na mesa automaticamente": {
        "en": "Arrange the objects on the bed automatically", "es": "Distribuir los objetos en la cama automáticamente",
        "fr": "Répartir automatiquement les objets sur le plateau", "de": "Objekte automatisch auf dem Druckbett anordnen",
        "it": "Disponi automaticamente gli oggetti sul piatto", "ja": "ベッド上のオブジェクトを自動配置"},
    "Posição": {"en": "Position", "es": "Posición", "fr": "Position", "de": "Position", "it": "Posizione", "ja": "位置"},
    "Posição do centro do objeto na mesa": {
        "en": "Position of the object's center on the bed", "es": "Posición del centro del objeto en la cama",
        "fr": "Position du centre de l'objet sur le plateau", "de": "Position der Objektmitte auf dem Druckbett",
        "it": "Posizione del centro dell'oggetto sul piatto", "ja": "ベッド上のオブジェクト中心の位置"},
    "Centralizar na mesa": {
        "en": "Center on bed", "es": "Centrar en la cama", "fr": "Centrer sur le plateau", "de": "Auf dem Druckbett zentrieren",
        "it": "Centra sul piatto", "ja": "ベッドの中央に配置"},
    "Dimensões": {"en": "Dimensions", "es": "Dimensiones", "fr": "Dimensions", "de": "Abmessungen", "it": "Dimensioni",
                  "ja": "寸法"},
    "Escala em relação ao tamanho original": {
        "en": "Scale relative to the original size", "es": "Escala respecto al tamaño original",
        "fr": "Échelle par rapport à la taille d'origine", "de": "Skalierung relativ zur Originalgröße",
        "it": "Scala rispetto alla dimensione originale", "ja": "元のサイズに対する倍率"},
    "Escala uniforme": {"en": "Uniform scale", "es": "Escala uniforme", "fr": "Échelle uniforme", "de": "Gleichmäßig skalieren",
                        "it": "Scala uniforme", "ja": "均等スケール"},
    "Mantém a proporção entre X, Y e Z ao redimensionar": {
        "en": "Keeps the X, Y and Z proportions when resizing", "es": "Mantiene la proporción entre X, Y y Z al redimensionar",
        "fr": "Conserve les proportions entre X, Y et Z lors du redimensionnement",
        "de": "Behält das Verhältnis von X, Y und Z beim Skalieren bei",
        "it": "Mantiene le proporzioni tra X, Y e Z durante il ridimensionamento", "ja": "サイズ変更時にX・Y・Zの比率を保持"},
    "Escala uniforme: {p}%": {
        "en": "Uniform scale: {p}%", "es": "Escala uniforme: {p}%", "fr": "Échelle uniforme : {p} %",
        "de": "Gleichmäßige Skalierung: {p} %", "it": "Scala uniforme: {p}%", "ja": "均等スケール: {p}%"},
    "Escala:  X {x}%  ·  Y {y}%  ·  Z {z}%": {
        "en": "Scale:  X {x}%  ·  Y {y}%  ·  Z {z}%", "es": "Escala:  X {x}%  ·  Y {y}%  ·  Z {z}%",
        "fr": "Échelle :  X {x} %  ·  Y {y} %  ·  Z {z} %", "de": "Skalierung:  X {x} %  ·  Y {y} %  ·  Z {z} %",
        "it": "Scala:  X {x}%  ·  Y {y}%  ·  Z {z}%", "ja": "スケール:  X {x}%  ·  Y {y}%  ·  Z {z}%"},
    "Rotação 90°": {"en": "Rotate 90°", "es": "Rotación 90°", "fr": "Rotation 90°", "de": "90°-Drehung",
                    "it": "Rotazione 90°", "ja": "90°回転"},
    "Para rotação livre, use Rotacionar (R) no menu do botão direito.": {
        "en": "For free rotation, use Rotate (R) in the right-click menu.",
        "es": "Para rotación libre, usa Rotar (R) en el menú del botón derecho.",
        "fr": "Pour une rotation libre, utilisez Pivoter (R) dans le menu du clic droit.",
        "de": "Für freie Drehung „Drehen“ (R) im Rechtsklick-Menü verwenden.",
        "it": "Per la rotazione libera usa Ruota (R) nel menu del tasto destro.",
        "ja": "自由回転は右クリックメニューの「回転」(R) を使用してください。"},
    "Redefinir transformações": {
        "en": "Reset transformations", "es": "Restablecer transformaciones", "fr": "Réinitialiser les transformations",
        "de": "Transformationen zurücksetzen", "it": "Reimposta trasformazioni", "ja": "変形をリセット"},
    "Restaura tamanho e rotação originais do objeto selecionado": {
        "en": "Restores the original size and rotation of the selected object",
        "es": "Restaura el tamaño y la rotación originales del objeto seleccionado",
        "fr": "Rétablit la taille et la rotation d'origine de l'objet sélectionné",
        "de": "Stellt Originalgröße und -drehung des ausgewählten Objekts wieder her",
        "it": "Ripristina dimensione e rotazione originali dell'oggetto selezionato",
        "ja": "選択したオブジェクトのサイズと回転を元に戻す"},
    "⚠ Objeto fora da área de impressão": {
        "en": "⚠ Object outside the print area", "es": "⚠ Objeto fuera del área de impresión",
        "fr": "⚠ Objet hors de la zone d'impression", "de": "⚠ Objekt außerhalb des Druckbereichs",
        "it": "⚠ Oggetto fuori dall'area di stampa", "ja": "⚠ オブジェクトが造形範囲外です"},
    "⚠ Há objetos fora da área de impressão": {
        "en": "⚠ Some objects are outside the print area", "es": "⚠ Hay objetos fuera del área de impresión",
        "fr": "⚠ Des objets sont hors de la zone d'impression", "de": "⚠ Einige Objekte liegen außerhalb des Druckbereichs",
        "it": "⚠ Alcuni oggetti sono fuori dall'area di stampa", "ja": "⚠ 造形範囲外のオブジェクトがあります"},
    "Objetos na mesa: {n}": {
        "en": "Objects on bed: {n}", "es": "Objetos en la cama: {n}", "fr": "Objets sur le plateau : {n}",
        "de": "Objekte auf dem Druckbett: {n}", "it": "Oggetti sul piatto: {n}", "ja": "ベッド上のオブジェクト: {n}"},
    "Objetos: {n}": {"en": "Objects: {n}", "es": "Objetos: {n}", "fr": "Objets : {n}", "de": "Objekte: {n}",
                     "it": "Oggetti: {n}", "ja": "オブジェクト: {n}"},

    # ---- aba Configurações ----
    "Exibição": {"en": "Display", "es": "Visualización", "fr": "Affichage", "de": "Anzeige", "it": "Visualizzazione",
                 "ja": "表示"},
    "Modo de renderização": {"en": "Render mode", "es": "Modo de renderizado", "fr": "Mode de rendu",
                             "de": "Darstellungsmodus", "it": "Modalità di rendering", "ja": "表示モード"},
    "Sólido": {"en": "Solid", "es": "Sólido", "fr": "Solide", "de": "Massiv", "it": "Solido", "ja": "ソリッド"},
    "Wireframe": {"en": "Wireframe", "es": "Alambre", "fr": "Filaire", "de": "Drahtgitter", "it": "Wireframe",
                  "ja": "ワイヤーフレーム"},
    "Sólido + wireframe": {"en": "Solid + wireframe", "es": "Sólido + alambre", "fr": "Solide + filaire",
                           "de": "Massiv + Drahtgitter", "it": "Solido + wireframe", "ja": "ソリッド + ワイヤーフレーム"},
    "Cor do objeto": {"en": "Object color", "es": "Color del objeto", "fr": "Couleur de l'objet", "de": "Objektfarbe",
                      "it": "Colore dell'oggetto", "ja": "オブジェクトの色"},
    "Exibir mesa": {"en": "Show bed", "es": "Mostrar cama", "fr": "Afficher le plateau", "de": "Druckbett anzeigen",
                    "it": "Mostra piatto", "ja": "ベッドを表示"},
    "Volume de impressão": {"en": "Build volume", "es": "Volumen de impresión", "fr": "Volume d'impression",
                            "de": "Bauraum", "it": "Volume di stampa", "ja": "造形サイズ"},
    "Largura (X)": {"en": "Width (X)", "es": "Ancho (X)", "fr": "Largeur (X)", "de": "Breite (X)", "it": "Larghezza (X)",
                    "ja": "幅 (X)"},
    "Profundidade (Y)": {"en": "Depth (Y)", "es": "Profundidad (Y)", "fr": "Profondeur (Y)", "de": "Tiefe (Y)",
                         "it": "Profondità (Y)", "ja": "奥行き (Y)"},
    "Altura (Z)": {"en": "Height (Z)", "es": "Altura (Z)", "fr": "Hauteur (Z)", "de": "Höhe (Z)", "it": "Altezza (Z)",
                   "ja": "高さ (Z)"},
    "Fatiador": {"en": "Slicer", "es": "Laminador", "fr": "Trancheur", "de": "Slicer", "it": "Slicer", "ja": "スライサー"},
    "Programa": {"en": "Program", "es": "Programa", "fr": "Programme", "de": "Programm", "it": "Programma", "ja": "プログラム"},
    "Outro…": {"en": "Other…", "es": "Otro…", "fr": "Autre…", "de": "Anderer…", "it": "Altro…", "ja": "その他…"},
    "Procurar executável…": {"en": "Browse for executable…", "es": "Buscar ejecutable…", "fr": "Rechercher l'exécutable…",
                             "de": "Programmdatei suchen…", "it": "Cerca eseguibile…", "ja": "実行ファイルを参照…"},
    "Não encontrado neste computador. Use “Procurar executável…”.": {
        "en": "Not found on this computer. Use “Browse for executable…”.",
        "es": "No encontrado en este equipo. Usa “Buscar ejecutable…”.",
        "fr": "Introuvable sur cet ordinateur. Utilisez « Rechercher l'exécutable… ».",
        "de": "Auf diesem Computer nicht gefunden. „Programmdatei suchen…“ verwenden.",
        "it": "Non trovato su questo computer. Usa “Cerca eseguibile…”.",
        "ja": "このPCに見つかりません。「実行ファイルを参照…」を使用してください。"},
    "Localizar o executável do {nome}": {
        "en": "Locate the {nome} executable", "es": "Localizar el ejecutable de {nome}",
        "fr": "Localiser l'exécutable de {nome}", "de": "Programmdatei von {nome} suchen",
        "it": "Trova l'eseguibile di {nome}", "ja": "{nome} の実行ファイルを指定"},
    "Selecionar o executável do fatiador": {
        "en": "Select the slicer executable", "es": "Seleccionar el ejecutable del laminador",
        "fr": "Sélectionner l'exécutable du trancheur", "de": "Programmdatei des Slicers wählen",
        "it": "Seleziona l'eseguibile dello slicer", "ja": "スライサーの実行ファイルを選択"},
    "{nome} não encontrado. Indique o local do executável.": {
        "en": "{nome} not found. Please locate the executable.", "es": "{nome} no encontrado. Indica dónde está el ejecutable.",
        "fr": "{nome} introuvable. Indiquez l'emplacement de l'exécutable.",
        "de": "{nome} nicht gefunden. Bitte Programmdatei angeben.",
        "it": "{nome} non trovato. Indica dove si trova l'eseguibile.", "ja": "{nome} が見つかりません。実行ファイルの場所を指定してください。"},
    "Não foi possível abrir no {nome}:": {
        "en": "Could not open in {nome}:", "es": "No se pudo abrir en {nome}:", "fr": "Impossible d'ouvrir dans {nome} :",
        "de": "Öffnen in {nome} nicht möglich:", "it": "Impossibile aprire in {nome}:", "ja": "{nome} で開けませんでした:"},
    "Abrindo no {nome}…": {"en": "Opening in {nome}…", "es": "Abriendo en {nome}…", "fr": "Ouverture dans {nome}…",
                           "de": "Wird in {nome} geöffnet…", "it": "Apertura in {nome}…", "ja": "{nome} で開いています…"},
    "Idioma": {"en": "Language", "es": "Idioma", "fr": "Langue", "de": "Sprache", "it": "Lingua", "ja": "言語"},
    "O novo idioma será aplicado quando o programa for reiniciado.": {
        "en": "The new language will be applied when the program restarts.",
        "es": "El nuevo idioma se aplicará al reiniciar el programa.",
        "fr": "La nouvelle langue sera appliquée au redémarrage du programme.",
        "de": "Die neue Sprache wird nach einem Neustart des Programms übernommen.",
        "it": "La nuova lingua verrà applicata al riavvio del programma.",
        "ja": "新しい言語はプログラムの再起動後に適用されます。"},
    "Reiniciar agora": {"en": "Restart now", "es": "Reiniciar ahora", "fr": "Redémarrer maintenant",
                        "de": "Jetzt neu starten", "it": "Riavvia ora", "ja": "今すぐ再起動"},
    "Depois": {"en": "Later", "es": "Más tarde", "fr": "Plus tard", "de": "Später", "it": "Più tardi", "ja": "後で"},
    "Definir como visualizador padrão": {
        "en": "Set as default viewer", "es": "Establecer como visor predeterminado",
        "fr": "Définir comme visionneuse par défaut", "de": "Als Standard-Viewer festlegen",
        "it": "Imposta come visualizzatore predefinito", "ja": "既定のビューアに設定"},
    "Faz os arquivos .stl, .3mf, .obj e .ply abrirem neste programa com dois cliques.": {
        "en": "Makes .stl, .3mf, .obj and .ply files open in this program with a double-click.",
        "es": "Hace que los archivos .stl, .3mf, .obj y .ply se abran en este programa con doble clic.",
        "fr": "Ouvre les fichiers .stl, .3mf, .obj et .ply dans ce programme par double-clic.",
        "de": ".stl-, .3mf-, .obj- und .ply-Dateien per Doppelklick in diesem Programm öffnen.",
        "it": "Fa aprire i file .stl, .3mf, .obj e .ply in questo programma con un doppio clic.",
        "ja": ".stl / .3mf / .obj / .ply ファイルをダブルクリックでこのプログラムで開きます。"},
    "Esta opção só está disponível no Windows.": {
        "en": "This option is only available on Windows.", "es": "Esta opción solo está disponible en Windows.",
        "fr": "Cette option n'est disponible que sous Windows.", "de": "Diese Option ist nur unter Windows verfügbar.",
        "it": "Questa opzione è disponibile solo su Windows.", "ja": "このオプションはWindowsでのみ利用できます。"},
    "Esta opção só funciona na versão .exe do programa.": {
        "en": "This option only works in the .exe version of the program.",
        "es": "Esta opción solo funciona en la versión .exe del programa.",
        "fr": "Cette option ne fonctionne que dans la version .exe du programme.",
        "de": "Diese Option funktioniert nur in der .exe-Version des Programms.",
        "it": "Questa opzione funziona solo nella versione .exe del programma.",
        "ja": "このオプションはプログラムの.exe版でのみ動作します。"},
    "Não foi possível registrar no Windows:": {
        "en": "Could not register with Windows:", "es": "No se pudo registrar en Windows:",
        "fr": "Impossible d'enregistrer dans Windows :", "de": "Registrierung in Windows fehlgeschlagen:",
        "it": "Impossibile registrare in Windows:", "ja": "Windowsに登録できませんでした:"},
    "Pronto! O programa foi registrado no Windows.\n\nNa janela “Abrir com” que vai aparecer, escolha "
    "“{app}” e clique em “Sempre”.\n\nPara os outros formatos (.3mf, .obj, .ply): clique com o botão direito "
    "no arquivo → Abrir com → Escolher outro aplicativo → {app} → Sempre.\n\nSe mudar o programa de pasta, "
    "use esta opção novamente.": {
        "en": "Done! The program has been registered with Windows.\n\nIn the “Open with” window that appears, choose "
              "“{app}” and click “Always”.\n\nFor the other formats (.3mf, .obj, .ply): right-click the file → "
              "Open with → Choose another app → {app} → Always.\n\nIf you move the program to another folder, use "
              "this option again.",
        "es": "¡Listo! El programa se registró en Windows.\n\nEn la ventana “Abrir con” que aparecerá, elige "
              "“{app}” y haz clic en “Siempre”.\n\nPara los demás formatos (.3mf, .obj, .ply): clic derecho en el "
              "archivo → Abrir con → Elegir otra aplicación → {app} → Siempre.\n\nSi mueves el programa a otra "
              "carpeta, usa esta opción de nuevo.",
        "fr": "Terminé ! Le programme a été enregistré dans Windows.\n\nDans la fenêtre « Ouvrir avec » qui va "
              "s'afficher, choisissez « {app} » puis « Toujours ».\n\nPour les autres formats (.3mf, .obj, .ply) : "
              "clic droit sur le fichier → Ouvrir avec → Choisir une autre application → {app} → Toujours.\n\n"
              "Si vous déplacez le programme, utilisez à nouveau cette option.",
        "de": "Fertig! Das Programm wurde in Windows registriert.\n\nWählen Sie im Fenster „Öffnen mit“ "
              "„{app}“ und klicken Sie auf „Immer“.\n\nFür die anderen Formate (.3mf, .obj, .ply): Rechtsklick auf "
              "die Datei → Öffnen mit → Andere App auswählen → {app} → Immer.\n\nWenn Sie das Programm in einen "
              "anderen Ordner verschieben, verwenden Sie diese Option erneut.",
        "it": "Fatto! Il programma è stato registrato in Windows.\n\nNella finestra “Apri con” che comparirà, "
              "scegli “{app}” e fai clic su “Sempre”.\n\nPer gli altri formati (.3mf, .obj, .ply): clic destro sul "
              "file → Apri con → Scegli un'altra app → {app} → Sempre.\n\nSe sposti il programma in un'altra "
              "cartella, usa di nuovo questa opzione.",
        "ja": "完了しました。プログラムをWindowsに登録しました。\n\n表示される「プログラムから開く」で"
              "「{app}」を選び、「常に使う」をクリックしてください。\n\nほかの形式 (.3mf, .obj, .ply) は、"
              "ファイルを右クリック → プログラムから開く → 別のアプリを選択 → {app} → 常に使う。\n\n"
              "プログラムのフォルダーを移動した場合は、もう一度このオプションを使用してください。"},

    # ---- menu do botão direito ----
    "Organizar automaticamente": {
        "en": "Auto-arrange", "es": "Organizar automáticamente", "fr": "Organiser automatiquement",
        "de": "Automatisch anordnen", "it": "Disponi automaticamente", "ja": "自動整列"},
    "Remover objeto": {"en": "Remove object", "es": "Quitar objeto", "fr": "Retirer l'objet", "de": "Objekt entfernen",
                       "it": "Rimuovi oggetto", "ja": "オブジェクトを削除"},
    "Desfazer": {"en": "Undo", "es": "Deshacer", "fr": "Annuler", "de": "Rückgängig", "it": "Annulla", "ja": "元に戻す"},
    "Refazer": {"en": "Redo", "es": "Rehacer", "fr": "Rétablir", "de": "Wiederholen", "it": "Ripeti", "ja": "やり直し"},
    "Salvar captura de tela (PNG)…": {
        "en": "Save screenshot (PNG)…", "es": "Guardar captura de pantalla (PNG)…", "fr": "Enregistrer une capture d'écran (PNG)…",
        "de": "Bildschirmfoto speichern (PNG)…", "it": "Salva screenshot (PNG)…", "ja": "スクリーンショットを保存 (PNG)…"},
    "Salvar captura de tela": {
        "en": "Save screenshot", "es": "Guardar captura de pantalla", "fr": "Enregistrer une capture d'écran",
        "de": "Bildschirmfoto speichern", "it": "Salva screenshot", "ja": "スクリーンショットを保存"},
    "Abrir no fatiador ({nome})": {
        "en": "Open in slicer ({nome})", "es": "Abrir en el laminador ({nome})", "fr": "Ouvrir dans le trancheur ({nome})",
        "de": "Im Slicer öffnen ({nome})", "it": "Apri nello slicer ({nome})", "ja": "スライサーで開く ({nome})"},
    "Ação desfeita": {"en": "Undone", "es": "Acción deshecha", "fr": "Action annulée", "de": "Rückgängig gemacht",
                      "it": "Azione annullata", "ja": "元に戻しました"},
    "Ação refeita": {"en": "Redone", "es": "Acción rehecha", "fr": "Action rétablie", "de": "Wiederhergestellt",
                     "it": "Azione ripetuta", "ja": "やり直しました"},

    # ---- diálogos ----
    "Cancelar": {"en": "Cancel", "es": "Cancelar", "fr": "Annuler", "de": "Abbrechen", "it": "Annulla", "ja": "キャンセル"},
    "Nenhum modelo 3D encontrado em:\n{c}": {
        "en": "No 3D models found in:\n{c}", "es": "No se encontraron modelos 3D en:\n{c}",
        "fr": "Aucun modèle 3D trouvé dans :\n{c}", "de": "Keine 3D-Modelle gefunden in:\n{c}",
        "it": "Nessun modello 3D trovato in:\n{c}", "ja": "3Dモデルが見つかりません:\n{c}"},
    "{arq} — selecionar modelos": {
        "en": "{arq} — select models", "es": "{arq} — seleccionar modelos", "fr": "{arq} — sélectionner les modèles",
        "de": "{arq} — Modelle auswählen", "it": "{arq} — seleziona modelli", "ja": "{arq} — モデルを選択"},
    "Modelos neste arquivo: {n}. Selecione os que deseja abrir:": {
        "en": "Models in this file: {n}. Select the ones to open:",
        "es": "Modelos en este archivo: {n}. Selecciona los que quieres abrir:",
        "fr": "Modèles dans ce fichier : {n}. Sélectionnez ceux à ouvrir :",
        "de": "Modelle in dieser Datei: {n}. Wählen Sie die zu öffnenden aus:",
        "it": "Modelli in questo file: {n}. Seleziona quelli da aprire:",
        "ja": "このファイルのモデル数: {n}。開くモデルを選択してください:"},
    "Selecionar todos": {"en": "Select all", "es": "Seleccionar todos", "fr": "Tout sélectionner", "de": "Alle auswählen",
                         "it": "Seleziona tutti", "ja": "すべて選択"},
    "Limpar seleção": {"en": "Clear selection", "es": "Borrar selección", "fr": "Effacer la sélection",
                       "de": "Auswahl aufheben", "it": "Cancella selezione", "ja": "選択を解除"},
    "Não foi possível abrir:": {"en": "Could not open:", "es": "No se pudo abrir:", "fr": "Impossible d'ouvrir :",
                                "de": "Öffnen nicht möglich:", "it": "Impossibile aprire:", "ja": "開けませんでした:"},
    "Objetos na mesa: {n}. O que deseja exportar?": {
        "en": "Objects on bed: {n}. What would you like to export?",
        "es": "Objetos en la cama: {n}. ¿Qué quieres exportar?",
        "fr": "Objets sur le plateau : {n}. Que voulez-vous exporter ?",
        "de": "Objekte auf dem Druckbett: {n}. Was möchten Sie exportieren?",
        "it": "Oggetti sul piatto: {n}. Cosa vuoi esportare?", "ja": "ベッド上のオブジェクト: {n}。何をエクスポートしますか?"},
    "Todos em um arquivo": {"en": "All in one file", "es": "Todos en un archivo", "fr": "Tous dans un fichier",
                            "de": "Alle in einer Datei", "it": "Tutti in un file", "ja": "すべてを1つのファイルに"},
    "Somente o selecionado": {"en": "Selected only", "es": "Solo el seleccionado", "fr": "Uniquement la sélection",
                              "de": "Nur das ausgewählte", "it": "Solo quello selezionato", "ja": "選択したもののみ"},
    "Não foi possível exportar:": {"en": "Could not export:", "es": "No se pudo exportar:", "fr": "Impossible d'exporter :",
                                   "de": "Export nicht möglich:", "it": "Impossibile esportare:", "ja": "エクスポートできませんでした:"},
    "Exportado: {c}": {"en": "Exported: {c}", "es": "Exportado: {c}", "fr": "Exporté : {c}", "de": "Exportiert: {c}",
                       "it": "Esportato: {c}", "ja": "エクスポートしました: {c}"},
    "Captura salva: {c}": {"en": "Screenshot saved: {c}", "es": "Captura guardada: {c}", "fr": "Capture enregistrée : {c}",
                           "de": "Bildschirmfoto gespeichert: {c}", "it": "Screenshot salvato: {c}",
                           "ja": "スクリーンショットを保存しました: {c}"},
    "Não foi possível salvar a captura de tela.": {
        "en": "Could not save the screenshot.", "es": "No se pudo guardar la captura de pantalla.",
        "fr": "Impossible d'enregistrer la capture d'écran.", "de": "Bildschirmfoto konnte nicht gespeichert werden.",
        "it": "Impossibile salvare lo screenshot.", "ja": "スクリーンショットを保存できませんでした。"},
    "Aconteceu um erro inesperado:": {
        "en": "An unexpected error occurred:", "es": "Ocurrió un error inesperado:", "fr": "Une erreur inattendue s'est produite :",
        "de": "Ein unerwarteter Fehler ist aufgetreten:", "it": "Si è verificato un errore imprevisto:",
        "ja": "予期しないエラーが発生しました:"},
    "Detalhes salvos em:": {"en": "Details saved to:", "es": "Detalles guardados en:", "fr": "Détails enregistrés dans :",
                            "de": "Details gespeichert in:", "it": "Dettagli salvati in:", "ja": "詳細の保存先:"},

    # ---- biblioteca ----
    "Pastas": {"en": "Folders", "es": "Carpetas", "fr": "Dossiers", "de": "Ordner", "it": "Cartelle", "ja": "フォルダー"},
    "Adicionar pasta…": {"en": "Add folder…", "es": "Añadir carpeta…", "fr": "Ajouter un dossier…", "de": "Ordner hinzufügen…",
                         "it": "Aggiungi cartella…", "ja": "フォルダーを追加…"},
    "Adicionar pasta à biblioteca": {
        "en": "Add folder to library", "es": "Añadir carpeta a la biblioteca", "fr": "Ajouter un dossier à la bibliothèque",
        "de": "Ordner zur Bibliothek hinzufügen", "it": "Aggiungi cartella alla libreria", "ja": "ライブラリにフォルダーを追加"},
    "Adicionar pasta à biblioteca…": {
        "en": "Add folder to library…", "es": "Añadir carpeta a la biblioteca…", "fr": "Ajouter un dossier à la bibliothèque…",
        "de": "Ordner zur Bibliothek hinzufügen…", "it": "Aggiungi cartella alla libreria…", "ja": "ライブラリにフォルダーを追加…"},
    "Remove a pasta da biblioteca (os arquivos não são apagados)": {
        "en": "Removes the folder from the library (files are not deleted)",
        "es": "Quita la carpeta de la biblioteca (los archivos no se borran)",
        "fr": "Retire le dossier de la bibliothèque (les fichiers ne sont pas supprimés)",
        "de": "Entfernt den Ordner aus der Bibliothek (Dateien werden nicht gelöscht)",
        "it": "Rimuove la cartella dalla libreria (i file non vengono eliminati)",
        "ja": "ライブラリからフォルダーを外します (ファイルは削除されません)"},
    "Incluir subpastas": {"en": "Include subfolders", "es": "Incluir subcarpetas", "fr": "Inclure les sous-dossiers",
                          "de": "Unterordner einbeziehen", "it": "Includi sottocartelle", "ja": "サブフォルダーを含める"},
    "Limpar cache de miniaturas": {
        "en": "Clear thumbnail cache", "es": "Borrar caché de miniaturas", "fr": "Vider le cache des miniatures",
        "de": "Vorschaubild-Cache leeren", "it": "Svuota cache delle miniature", "ja": "サムネイルキャッシュを削除"},
    "Apaga as miniaturas salvas. Elas são geradas de novo quando necessário.": {
        "en": "Deletes saved thumbnails. They are regenerated when needed.",
        "es": "Borra las miniaturas guardadas. Se vuelven a generar cuando hace falta.",
        "fr": "Supprime les miniatures enregistrées. Elles sont régénérées au besoin.",
        "de": "Löscht gespeicherte Vorschaubilder. Sie werden bei Bedarf neu erstellt.",
        "it": "Elimina le miniature salvate. Vengono rigenerate quando serve.",
        "ja": "保存されたサムネイルを削除します。必要に応じて再生成されます。"},
    "Miniaturas em cache: {n} ({mb} MB)": {
        "en": "Cached thumbnails: {n} ({mb} MB)", "es": "Miniaturas en caché: {n} ({mb} MB)",
        "fr": "Miniatures en cache : {n} ({mb} Mo)", "de": "Vorschaubilder im Cache: {n} ({mb} MB)",
        "it": "Miniature in cache: {n} ({mb} MB)", "ja": "キャッシュ済みサムネイル: {n} ({mb} MB)"},
    "Cache vazio": {"en": "Cache is empty", "es": "Caché vacía", "fr": "Cache vide", "de": "Cache ist leer",
                    "it": "Cache vuota", "ja": "キャッシュは空です"},
    "Apagar as miniaturas salvas ({n} · {mb} MB)?\n\nSeus modelos não serão alterados. As miniaturas serão "
    "geradas de novo quando necessário.": {
        "en": "Delete the saved thumbnails ({n} · {mb} MB)?\n\nYour models will not be changed. Thumbnails will be "
              "regenerated when needed.",
        "es": "¿Borrar las miniaturas guardadas ({n} · {mb} MB)?\n\nTus modelos no se modificarán. Las miniaturas se "
              "volverán a generar cuando haga falta.",
        "fr": "Supprimer les miniatures enregistrées ({n} · {mb} Mo) ?\n\nVos modèles ne seront pas modifiés. Les "
              "miniatures seront régénérées au besoin.",
        "de": "Gespeicherte Vorschaubilder löschen ({n} · {mb} MB)?\n\nIhre Modelle werden nicht verändert. Die "
              "Vorschaubilder werden bei Bedarf neu erstellt.",
        "it": "Eliminare le miniature salvate ({n} · {mb} MB)?\n\nI tuoi modelli non verranno modificati. Le "
              "miniature verranno rigenerate quando serve.",
        "ja": "保存されたサムネイル ({n} · {mb} MB) を削除しますか?\n\nモデルは変更されません。サムネイルは"
              "必要に応じて再生成されます。"},
    "Buscar por nome…": {"en": "Search by name…", "es": "Buscar por nombre…", "fr": "Rechercher par nom…",
                         "de": "Nach Namen suchen…", "it": "Cerca per nome…", "ja": "名前で検索…"},
    "Atualizar": {"en": "Refresh", "es": "Actualizar", "fr": "Actualiser", "de": "Aktualisieren", "it": "Aggiorna",
                  "ja": "更新"},
    "Nenhuma pasta na biblioteca.\nUse “Adicionar pasta…” para começar.": {
        "en": "No folders in the library.\nUse “Add folder…” to get started.",
        "es": "No hay carpetas en la biblioteca.\nUsa “Añadir carpeta…” para empezar.",
        "fr": "Aucun dossier dans la bibliothèque.\nUtilisez « Ajouter un dossier… » pour commencer.",
        "de": "Keine Ordner in der Bibliothek.\nMit „Ordner hinzufügen…“ beginnen.",
        "it": "Nessuna cartella nella libreria.\nUsa “Aggiungi cartella…” per iniziare.",
        "ja": "ライブラリにフォルダーがありません。\n「フォルダーを追加…」から始めましょう。"},
    "Nenhuma pasta na biblioteca.\nClique em “+” para adicionar.": {
        "en": "No folders in the library.\nClick “+” to add one.",
        "es": "No hay carpetas en la biblioteca.\nHaz clic en “+” para añadir.",
        "fr": "Aucun dossier dans la bibliothèque.\nCliquez sur « + » pour en ajouter.",
        "de": "Keine Ordner in der Bibliothek.\nZum Hinzufügen auf „+“ klicken.",
        "it": "Nessuna cartella nella libreria.\nFai clic su “+” per aggiungerne una.",
        "ja": "ライブラリにフォルダーがありません。\n「+」をクリックして追加します。"},
    "Duplo clique: abrir   ·   Botão direito: mais opções": {
        "en": "Double-click: open   ·   Right-click: more options",
        "es": "Doble clic: abrir   ·   Botón derecho: más opciones",
        "fr": "Double-clic : ouvrir   ·   Clic droit : plus d'options",
        "de": "Doppelklick: öffnen   ·   Rechtsklick: weitere Optionen",
        "it": "Doppio clic: apri   ·   Tasto destro: altre opzioni",
        "ja": "ダブルクリック: 開く   ·   右クリック: その他のオプション"},
    "Detalhes": {"en": "Details", "es": "Detalles", "fr": "Détails", "de": "Details", "it": "Dettagli", "ja": "詳細"},
    "Todas as pastas": {"en": "All folders", "es": "Todas las carpetas", "fr": "Tous les dossiers", "de": "Alle Ordner",
                        "it": "Tutte le cartelle", "ja": "すべてのフォルダー"},
    "Modelos: {n}": {"en": "Models: {n}", "es": "Modelos: {n}", "fr": "Modèles : {n}", "de": "Modelle: {n}",
                     "it": "Modelli: {n}", "ja": "モデル: {n}"},
    "(limite de {n})": {"en": "(limit {n})", "es": "(límite de {n})", "fr": "(limite de {n})", "de": "(Limit {n})",
                        "it": "(limite di {n})", "ja": "(上限 {n})"},
    "Selecione um modelo\npara ver os detalhes": {
        "en": "Select a model\nto see its details", "es": "Selecciona un modelo\npara ver los detalles",
        "fr": "Sélectionnez un modèle\npour voir les détails", "de": "Modell auswählen,\num Details zu sehen",
        "it": "Seleziona un modello\nper vedere i dettagli", "ja": "モデルを選択すると\n詳細が表示されます"},
    "Gerando miniatura…": {"en": "Generating thumbnail…", "es": "Generando miniatura…", "fr": "Création de la miniature…",
                           "de": "Vorschaubild wird erstellt…", "it": "Generazione miniatura…", "ja": "サムネイルを生成中…"},
    "Triângulos": {"en": "Triangles", "es": "Triángulos", "fr": "Triangles", "de": "Dreiecke", "it": "Triangoli",
                   "ja": "三角形"},
    "Modelos 3D no arquivo": {"en": "3D models in file", "es": "Modelos 3D en el archivo", "fr": "Modèles 3D dans le fichier",
                              "de": "3D-Modelle in der Datei", "it": "Modelli 3D nel file", "ja": "ファイル内の3Dモデル"},
    "arquivo .zip ilegível": {"en": "unreadable .zip file", "es": "archivo .zip ilegible", "fr": "fichier .zip illisible",
                              "de": "unlesbare .zip-Datei", "it": "file .zip illeggibile", "ja": "読み取れない.zipファイル"},
    "Tamanho": {"en": "Size", "es": "Tamaño", "fr": "Taille", "de": "Größe", "it": "Dimensione", "ja": "サイズ"},
    "Modificado em": {"en": "Modified", "es": "Modificado", "fr": "Modifié le", "de": "Geändert am", "it": "Modificato il",
                      "ja": "更新日時"},
    "Abrir {n} modelos juntos": {
        "en": "Open {n} models together", "es": "Abrir {n} modelos juntos", "fr": "Ouvrir {n} modèles ensemble",
        "de": "{n} Modelle zusammen öffnen", "it": "Apri {n} modelli insieme", "ja": "{n} 個のモデルをまとめて開く"},
    "Adicionar à mesa": {"en": "Add to bed", "es": "Añadir a la cama", "fr": "Ajouter au plateau",
                         "de": "Zum Druckbett hinzufügen", "it": "Aggiungi al piatto", "ja": "ベッドに追加"},
    "Mostrar na pasta": {"en": "Show in folder", "es": "Mostrar en la carpeta", "fr": "Afficher dans le dossier",
                         "de": "Im Ordner anzeigen", "it": "Mostra nella cartella", "ja": "フォルダーで表示"},

    # ---- mensagens de leitura de arquivos ----
    "O arquivo está vazio ou corrompido.": {
        "en": "The file is empty or corrupted.", "es": "El archivo está vacío o dañado.", "fr": "Le fichier est vide ou corrompu.",
        "de": "Die Datei ist leer oder beschädigt.", "it": "Il file è vuoto o danneggiato.", "ja": "ファイルが空か破損しています。"},
    "Não foi possível ler este arquivo como STL.": {
        "en": "Could not read this file as STL.", "es": "No se pudo leer este archivo como STL.",
        "fr": "Impossible de lire ce fichier en tant que STL.", "de": "Diese Datei konnte nicht als STL gelesen werden.",
        "it": "Impossibile leggere questo file come STL.", "ja": "このファイルをSTLとして読み込めませんでした。"},
    "Nenhum triângulo encontrado neste arquivo.": {
        "en": "No triangles found in this file.", "es": "No se encontraron triángulos en este archivo.",
        "fr": "Aucun triangle trouvé dans ce fichier.", "de": "Keine Dreiecke in dieser Datei gefunden.",
        "it": "Nessun triangolo trovato in questo file.", "ja": "このファイルに三角形が見つかりません。"},
    "O arquivo não tem triângulos válidos.": {
        "en": "The file has no valid triangles.", "es": "El archivo no tiene triángulos válidos.",
        "fr": "Le fichier ne contient aucun triangle valide.", "de": "Die Datei enthält keine gültigen Dreiecke.",
        "it": "Il file non contiene triangoli validi.", "ja": "ファイルに有効な三角形がありません。"},
    "Este 3MF está corrompido (não é um arquivo compactado válido).": {
        "en": "This 3MF is corrupted (not a valid compressed file).",
        "es": "Este 3MF está dañado (no es un archivo comprimido válido).",
        "fr": "Ce 3MF est corrompu (ce n'est pas une archive valide).",
        "de": "Diese 3MF-Datei ist beschädigt (kein gültiges Archiv).",
        "it": "Questo 3MF è danneggiato (non è un archivio valido).", "ja": "この3MFは破損しています (有効な圧縮ファイルではありません)。"},
    "O 3MF aponta para uma parte que não existe: {p}": {
        "en": "The 3MF refers to a part that does not exist: {p}", "es": "El 3MF hace referencia a una parte inexistente: {p}",
        "fr": "Le 3MF fait référence à une partie inexistante : {p}", "de": "Die 3MF verweist auf einen nicht vorhandenen Teil: {p}",
        "it": "Il 3MF fa riferimento a una parte inesistente: {p}", "ja": "3MFが存在しないパーツを参照しています: {p}"},
    "Nenhuma peça encontrada dentro deste 3MF.": {
        "en": "No parts found inside this 3MF.", "es": "No se encontraron piezas dentro de este 3MF.",
        "fr": "Aucune pièce trouvée dans ce 3MF.", "de": "Keine Teile in dieser 3MF-Datei gefunden.",
        "it": "Nessun pezzo trovato in questo 3MF.", "ja": "この3MFにパーツが見つかりません。"},
    "Não foi possível ler este arquivo como PLY.": {
        "en": "Could not read this file as PLY.", "es": "No se pudo leer este archivo como PLY.",
        "fr": "Impossible de lire ce fichier en tant que PLY.", "de": "Diese Datei konnte nicht als PLY gelesen werden.",
        "it": "Impossibile leggere questo file come PLY.", "ja": "このファイルをPLYとして読み込めませんでした。"},
    "Este PLY não tem faces (parece ser só uma nuvem de pontos).": {
        "en": "This PLY has no faces (it looks like a point cloud).",
        "es": "Este PLY no tiene caras (parece una nube de puntos).",
        "fr": "Ce PLY n'a pas de faces (il semble s'agir d'un nuage de points).",
        "de": "Diese PLY-Datei hat keine Flächen (offenbar eine Punktwolke).",
        "it": "Questo PLY non ha facce (sembra una nuvola di punti).", "ja": "このPLYには面がありません (点群のようです)。"},
    "Formato de PLY desconhecido.": {
        "en": "Unknown PLY format.", "es": "Formato PLY desconocido.", "fr": "Format PLY inconnu.",
        "de": "Unbekanntes PLY-Format.", "it": "Formato PLY sconosciuto.", "ja": "不明なPLY形式です。"},

    # ---- biblioteca por pastas (v1.4) ----
    "Voltar": {"en": "Back", "es": "Volver", "fr": "Retour", "de": "Zurück", "it": "Indietro", "ja": "戻る"},
    "Voltar para a pasta anterior": {
        "en": "Go back to the previous folder", "es": "Volver a la carpeta anterior", "fr": "Revenir au dossier précédent",
        "de": "Zurück zum vorherigen Ordner", "it": "Torna alla cartella precedente", "ja": "前のフォルダーに戻る"},
    "Resultados da busca": {"en": "Search results", "es": "Resultados de la búsqueda", "fr": "Résultats de la recherche",
                            "de": "Suchergebnisse", "it": "Risultati della ricerca", "ja": "検索結果"},
    "Entrar na pasta": {"en": "Open folder", "es": "Entrar en la carpeta", "fr": "Ouvrir le dossier",
                        "de": "Ordner öffnen", "it": "Apri cartella", "ja": "フォルダーを開く"},
    "Abrir todos juntos": {"en": "Open all together", "es": "Abrir todos juntos", "fr": "Tout ouvrir ensemble",
                           "de": "Alle zusammen öffnen", "it": "Apri tutti insieme", "ja": "すべてまとめて開く"},
    "Adicionar todos à mesa": {"en": "Add all to bed", "es": "Añadir todos a la cama", "fr": "Tout ajouter au plateau",
                               "de": "Alle zum Druckbett hinzufügen", "it": "Aggiungi tutti al piatto",
                               "ja": "すべてベッドに追加"},
    "Mostrar no Explorer": {"en": "Show in Explorer", "es": "Mostrar en el Explorador", "fr": "Afficher dans l'Explorateur",
                            "de": "Im Explorer anzeigen", "it": "Mostra in Esplora risorse", "ja": "エクスプローラーで表示"},
    "Subpastas": {"en": "Subfolders", "es": "Subcarpetas", "fr": "Sous-dossiers", "de": "Unterordner", "it": "Sottocartelle",
                  "ja": "サブフォルダー"},
    "Tamanho total": {"en": "Total size", "es": "Tamaño total", "fr": "Taille totale", "de": "Gesamtgröße",
                      "it": "Dimensione totale", "ja": "合計サイズ"},
    "Abrir {n} modelos de uma vez? Isso pode demorar um pouco.": {
        "en": "Open {n} models at once? This may take a while.",
        "es": "¿Abrir {n} modelos a la vez? Puede tardar un poco.",
        "fr": "Ouvrir {n} modèles à la fois ? Cela peut prendre un moment.",
        "de": "{n} Modelle auf einmal öffnen? Das kann etwas dauern.",
        "it": "Aprire {n} modelli contemporaneamente? Potrebbe volerci un po'.",
        "ja": "{n} 個のモデルを一度に開きますか? 少し時間がかかる場合があります。"},
    "Miniaturas": {"en": "Thumbnails", "es": "Miniaturas", "fr": "Miniatures", "de": "Miniaturen", "it": "Miniature",
                   "ja": "サムネイル"},
    "Lista": {"en": "List", "es": "Lista", "fr": "Liste", "de": "Liste", "it": "Elenco", "ja": "一覧"},
    "Mostrar como miniaturas": {"en": "Show as thumbnails", "es": "Mostrar como miniaturas", "fr": "Afficher en miniatures",
                                "de": "Als Miniaturen anzeigen", "it": "Mostra come miniature", "ja": "サムネイルで表示"},
    "Mostrar como lista": {"en": "Show as list", "es": "Mostrar como lista", "fr": "Afficher en liste",
                           "de": "Als Liste anzeigen", "it": "Mostra come elenco", "ja": "一覧で表示"},
    "Tamanho das miniaturas (Ctrl + roda do mouse)": {
        "en": "Thumbnail size (Ctrl + mouse wheel)", "es": "Tamaño de las miniaturas (Ctrl + rueda del ratón)",
        "fr": "Taille des miniatures (Ctrl + molette)", "de": "Miniaturgröße (Strg + Mausrad)",
        "it": "Dimensione miniature (Ctrl + rotella del mouse)", "ja": "サムネイルのサイズ (Ctrl + マウスホイール)"},
}
