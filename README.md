# PDFx

Leitor de documentos para **Windows** inspirado no [Evince](https://gitlab.gnome.org/GNOME/evince), o visualizador de documentos do GNOME.

Formatos: **PDF**, XPS/OXPS, EPUB, MOBI, FB2, CBZ, SVG, TXT e imagens (PNG, JPG, TIFF…).

## Recursos

- Visual no estilo do Evince/Adwaita: barra de título integrada (headerbar), seletor de página "1 de 14", zoom "100% ▾", barra lateral com miniaturas, sumário e marcadores
- Tela inicial com os documentos recentes (com miniaturas)
- Rolagem contínua ou página a página, modo de duas páginas, rotação, cores invertidas (modo noturno)
- Zoom: ajustar à largura, ajustar à página ou de 10% a 800% (Ctrl+roda do mouse)
- Busca incremental com destaque dos resultados
- Seleção e cópia de texto, links clicáveis
- Tela cheia (F11) e modo apresentação (F5)
- Impressão, "Salvar uma cópia", propriedades do documento
- Lembra a página, o zoom e a rotação de cada documento
- Recarrega sozinho quando o arquivo muda no disco
- Documentos protegidos por senha

Os atalhos de teclado estão no menu ☰ → **Atalhos de teclado**.

## Rodar a partir do código

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m pdfx [arquivo.pdf]
```

## Gerar o executável e o instalador

Pré-requisito para o instalador: [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`).

```powershell
.\build.ps1
```

Resultado:

- `dist\PDFx\PDFx.exe`: o programa (pasta portátil)
- `dist\installer\PDFx-Setup-<versão>.exe`: o instalador

O instalador não pede administrador. Ele cria um atalho no menu Iniciar (e, se você quiser, na área de trabalho) e adiciona o PDFx ao menu **Abrir com** dos formatos suportados. O Windows não deixa um instalador escolher o programa padrão: para isso, clique com o botão direito em um PDF → **Abrir com** → **Escolher outro aplicativo** → **PDFx** → marque **Sempre usar este aplicativo**.

## Estrutura

| Arquivo | Função |
|---|---|
| `pdfx/app.py` | ponto de entrada, gerencia as janelas (uma por documento) |
| `pdfx/main_window.py` | janela principal, ações e menu |
| `pdfx/view.py` | área de visualização: layout das páginas, renderização em blocos, seleção e links |
| `pdfx/document.py` | acesso ao documento via PyMuPDF (MuPDF) |
| `pdfx/headerbar.py` | barra de título no estilo GNOME |
| `pdfx/frameless.py` | janela sem moldura do Windows, mantendo o Aero Snap e o redimensionamento |
| `pdfx/sidebar.py` | miniaturas, sumário e marcadores |
| `pdfx/search.py` | busca incremental e barra de busca |
| `pdfx/recent.py` | tela de documentos recentes |
| `pdfx/theme.py`, `pdfx/icons.py` | tema Adwaita e ícones simbólicos |

Se a barra de título personalizada der algum problema no seu Windows, rode com a variável `PDFX_NATIVE_FRAME=1` para usar a moldura padrão.

Erros inesperados são gravados em `%LOCALAPPDATA%\PDFx\pdfx-erros.log`.

## Licenças

Uso pessoal. O PDFx usa o PyMuPDF/MuPDF (AGPL) e o Qt/PySide6 (LGPL). O visual e o comportamento seguem o Evince (GPL), mas nenhum código dele foi copiado.
