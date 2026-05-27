### **Documento de Design de Software (SDD) \- MagScan**

### **Parte 1: Escopo e Visão Geral (Rascunho)**

**1.1. Objetivo do Sistema** O projeto consiste no desenvolvimento de um sistema embarcado (Edge AI) focado na identificação automatizada e catalogação de cartas de *Magic: The Gathering*. O sistema deve ser capaz de capturar a imagem de uma carta física, isolá-la geometricamente, extrair o título utilizando Reconhecimento Óptico de Caracteres (OCR) e cruzar esse resultado com um banco de dados otimizado para inserir a carta de forma autônoma em um arquivo de inventário (JSON).

**1.2. Filosofia do MVP (Minimum Viable Product)** O sistema foi projetado para operar com foco extremo em velocidade e eficiência computacional. A prioridade fundamental nesta fase é a consistência na identificação precisa do **nome** da carta, operando inteiramente offline no momento da captura para contornar gargalos de rede e processamento.

**1.3. O que está dentro do Escopo (In-Scope)**

* Captura de frames utilizando uma webcam configurada com parâmetros rigorosamente estáticos (com *auto-exposure*, *auto-focus* e *auto white balance* desativados para evitar a quebra do *thresholding*).  
* Detecção e planificação da carta utilizando metodologias clássicas de Visão Computacional (OpenCV), baseando-se em proporções matemáticas conhecidas das cartas (aproximadamente 63/88).  
* Extração de texto cirúrgica, focada exclusivamente na barra de título (recorte dos \~11% superiores da carta planificada).  
* Correção de leitura via algoritmos de tolerância a falhas (*Fuzzy Matching* via RapidFuzz) contra um banco de dados relacional local indexado.  
* Exportação assíncrona do inventário processado.

**1.4. O que está fora do Escopo no MVP (Out-of-Scope)**

* **Identificação exata de edição/impressão:** Evitada no primeiro momento devido à latência gerada por chamadas de API em tempo real (como o Scryfall) e ao peso de realizar o download e a comparação de dezenas de variantes de artes idênticas em lote.  
* **Processamento pesado de dados no dispositivo de borda:** O processamento intenso (como o download do *bulk data* e a estruturação do banco de dados) deve ser transferido para um PC padrão. O microcomputador embarcado será responsável apenas por rodar o *runtime* otimizado.  
* **Modelos complexos de Inteligência Artificial para detecção:** A detecção da carta evitará inicialmente redes neurais pesadas, priorizando manipulação geométrica clássica de matrizes para preservar o processamento e a memória do hardware.

### **Parte 2: Arquitetura e Pipeline de Dados (Fluxo Híbrido)**

**2.1. Divisão de Responsabilidades (Edge vs. Host)** Para manter a latência de reconhecimento em níveis aceitáveis, a arquitetura exige uma divisão estrita de processamento:

* **Host (PC Base \- Processamento Pesado):** Um script rodado esporadicamente em um computador padrão. Ele baixa o *Bulk Data* do Scryfall, extrai os links das artes, faz o download temporário, gera o `dHash` (ou `pHash`) de 64-bits de cada impressão e compila tudo em um banco de dados relacional local (SQLite). Em seguida, esse arquivo `.db` otimizado é transferido para o embarcado.  
* **Edge (Orange Pi Zero 2 \- Runtime):** O hardware de borda atua apenas no momento da captura. Ele não acessa a internet nem baixa imagens. Todo o cruzamento de texto (OCR) e comparação de imagem (Hash) ocorre contra o banco SQLite local previamente alimentado.

**2.2. Pipeline de Processamento (O Ciclo de Vida da Carta)** O fluxo de um frame capturado até o registro no inventário obedece a uma ordem sequencial de eliminação:

1. **Captura e Detecção (Visão):** A câmera lê o frame. O algoritmo busca o maior contorno de 4 pontas que obedeça à razão de proporção de uma carta de MTG (aproximadamente `0.68 < ratio < 0.75`).  
2. **Planificação (Warp Perspective):** A carta é matematicamente "achatada" e cortada para uma resolução padronizada (ex: 744x1039 pixels), eliminando distorções de ângulo.  
3. **Filtragem de Texto (Descoberta):**  
   * O sistema recorta os \~11% superiores da carta (Caixa de Título).  
   * Aplica-se tons de cinza e binarização (P\&B puro).  
   * O Pytesseract lê os caracteres restringindo-se a uma *whitelist* alfanumérica.  
   * O motor de *Fuzzy Matching* (RapidFuzz) cruza o resultado sujo do OCR com a tabela de nomes únicos no SQLite, devolvendo o Nome oficial da carta.  
4. **Verificação de Arte (Confirmação \- O "Tiro de Sniper"):**  
   * Com o Nome em mãos, o banco retorna apenas as variantes existentes daquela carta (ex: 5 hashes diferentes para 5 impressões distintas de *Sol Ring*).  
   * O sistema recorta a Caixa de Arte da carta planificada, reduz a resolução e calcula o seu `dHash` local.  
   * Calcula-se a Distância de Hamming apenas contra aqueles 5 hashes. A arte que apresentar a menor distância (maior similaridade) é eleita como a edição correta.  
5. **Persistência (Registro):** O Nome, Edição, ID do Scryfall e o Timestamp são inseridos de forma assíncrona no `inventario.json` (ou tabela de coleção), sem travar a interface de captura de vídeo para a próxima carta.

**2.3. Modularização do Código** Para refletir esse pipeline, os scripts deverão adotar a seguinte organização arquitetural:

* `main.py`: O maestro. Gerencia o loop da câmera e as chamadas assíncronas (VideoThread).  
* `card_vision.py`: Isola a matemática. Faz a detecção de bordas, o *warp perspective* e entrega os recortes (Título e Arte).  
* `text_extractor.py`: Configurações de pré-processamento de imagem e chamadas otimizadas do Tesseract.  
* `hash_matcher.py` *(Novo)*: Recebe o recorte da arte, gera o hash matemático e calcula a Distância de Hamming.  
* `database.py`: Concentra todas as rotinas SQLite (índices, consultas rápidas e o cache em memória).

### **Parte 3: Hardware e Ambiente Físico**

**3.1. Unidade de Processamento (Edge Device)** O "cérebro" do sistema será o **Orange Pi Zero 2** (com processador Allwinner H618 e 1GB de RAM).

* **Sistema Operacional:** Recomendado o uso de uma distribuição enxuta sem interface gráfica pesada (como Armbian ou Debian Server) para preservar o máximo de memória RAM e ciclos de CPU para o pipeline do OpenCV e do SQLite.  
* **Refrigeração:** O processamento contínuo de matrizes de vídeo no OpenCV gera estresse térmico. Um dissipador passivo aliado a um micro-cooler é obrigatório para evitar o *thermal throttling* (redução de clock por alta temperatura).

**3.2. Estrutura Física e Prototipagem (A "Caixa Escura")** A precisão do algoritmo de OCR e do *dHash* depende de consistência geométrica. A câmera e a base de leitura da carta não podem se mover um milímetro sequer.

* O design estrutural do scanner deve assumir o formato de uma "caixa" ou "torre" fechada.  
* A prototipagem rápida da carcaça na Bambu Lab A1 permitirá iterar sobre a distância focal ideal. O material de impressão (preferencialmente PETG sólido ou ABS/ASA) deve ser **100% opaco**.  
* **Objetivo:** Isolar completamente a carta da iluminação externa do ambiente (janelas, lâmpadas do teto). O sistema deve ditar sua própria iluminação, sem interferência de sombras variáveis.

**3.3. Configuração de Câmera e Parametrização Restrita** A escolha da webcam USB exige capacidade macro (foco nítido a curta distância). A regra de ouro para o driver da câmera (geralmente controlado via `v4l2-ctl` no Linux) é a **desativação total da inteligência da câmera**:

* **Desativar Auto-Focus (Foco Automático):** A distância entre a lente e a mesa será cravada no design 3D. O foco deve ser ajustado manualmente na montagem e travado via software. Se a câmera tentar focar a mão do usuário inserindo a carta, o frame ficará borrado.  
* **Desativar Auto-Exposure (Exposição Automática):** O brilho do sensor deve ser fixo. Cartas majoritariamente brancas (como um plains) farão a câmera escurecer a imagem; cartas pretas farão a câmera estourar o brilho. Isso destruiria o parâmetro de *thresholding* (P\&B) do OCR.  
* **Desativar Auto-White-Balance (Balanço de Branco):** As cores também devem ser fixadas para garantir a estabilidade do contraste antes da conversão para tons de cinza.

**3.4. Controle de Iluminação (A Batalha contra Foil e Sleeves)** *Magic: The Gathering* é repleto de superfícies reflexivas (cartas *Foil* e os plásticos brilhantes dos *Inner Sleeves*). Reflexos criam manchas brancas ("estouros") que cegam o OCR e alteram os gradientes do *dHash*.

* **Fonte de Luz:** Um anel de LED branco posicionado ao redor ou perfeitamente alinhado com a lente da câmera.  
* **Difusor:** Os LEDs nunca podem apontar diretamente para a carta na forma de luz dura. É obrigatório o uso de um difusor (que pode ser uma placa de acrílico translúcido ou uma peça impressa fina em PLA branco leitoso) na frente do LED para espalhar a luz suavemente sobre a superfície, dissipando os focos de brilho ("*glare*").

### **Parte 4: Processamento de Imagem e Visão Computacional**

**4.1. Otimização de Entrada (Downscaling)** Para não sobrecarregar o hardware, a detecção geométrica não é feita na resolução máxima da câmera.

* O frame capturado em alta resolução (ex: 1080p) é imediatamente clonado e redimensionado para uma escala menor (ex: largura de 600 pixels) apenas para a etapa de busca.  
* O algoritmo encontra as coordenadas na imagem pequena e, matematicamente, as multiplica pela escala original para recortar a imagem em alta resolução no final.

**4.2. Pipeline de Pré-Processamento (Isolando a Forma)** O objetivo desta fase é ignorar as cores e a arte da carta, forçando o algoritmo a enxergar apenas a sua borda externa contra o fundo escuro da estrutura.

1. **Grayscale:** Conversão imediata do frame para tons de cinza.  
2. **Suavização (Blur):** Aplicação de um *Gaussian Blur* (ou *Bilateral Filter*). Isso é vital para "borrar" a textura interna da carta, ruídos da câmera e eventuais granulações de impressão, evitando que o algoritmo confunda a arte interna com as bordas reais da carta.  
3. **Canny Edge Detection:** O algoritmo de detecção de bordas puro. Ele mapeia os gradientes de cor mais fortes (o limite entre a borda da carta e a base escura do scanner), gerando uma imagem preta com as linhas de contorno em branco.  
4. **Morfologia Matemática (Dilation/Erosion):** Como a luz pode causar falhas microscópicas na linha detectada pelo Canny (deixando o contorno "aberto"), aplica-se uma dilatação matricial leve para fechar as linhas, garantindo contornos contínuos.

**4.3. Busca e Validação de Contornos (A Matemática da Carta)** Com as linhas traçadas, o `cv2.findContours` varre a imagem buscando formas fechadas. Para evitar que o sistema confunda um reflexo quadrado ou uma poeira com uma carta, aplicam-se filtros rigorosos:

* **Filtro de Área:** Descarta qualquer contorno pequeno demais.  
* **Filtro de Vértices:** O algoritmo simplifica o formato geométrico (aproximação poligonal). Se a forma tiver exatamente 4 pontas (um quadrilátero), ela passa para a próxima fase.  
* **Filtro de Proporção (O "Fator MTG"):** Uma carta padrão mede 63mm x 88mm, o que nos dá uma razão de aspecto (largura/altura) de aproximadamente **0.715**. O sistema calcula a razão geométrica do quadrilátero detectado e exige que ele esteja no intervalo de `0.68 < ratio < 0.75`. Isso garante que apenas cartas de TCG sejam processadas.

**4.4. Retificação e Planificação (Perspective Transform)** Quando o usuário coloca a carta no scanner, ela pode estar levemente torta ou fora de esquadro.

* O algoritmo coleta os 4 vértices do quadrilátero validado e os mapeia para as 4 pontas de um retângulo perfeito em uma resolução cravada de **744x1039 pixels** (proporção exata em alta resolução).  
* A função `cv2.warpPerspective` "estica e achata" a imagem capturada para caber nessa matriz.  
* **O Resultado:** Uma matriz de imagem limpa, perfeitamente reta, sem nenhum fundo (apenas a carta). É a partir deste arquivo estabilizado que faremos o "recorte" da barra de título e da caixa de arte na próxima etapa.

### **Parte 5: Estratégia de Extração e Tratamento de Texto**

**5.1. Isolamento da Região de Interesse (Crop do Título)** O Tesseract perde muito tempo (e precisão) tentando ler caixas de texto que não nos interessam, como regras, custo de mana, *flavor text* ou o nome do ilustrador.

* Após a planificação da carta na Parte 4 (matriz de 744x1039), o sistema fará um recorte geométrico exato dos **\~11% a 12% superiores** da imagem.  
* Esse recorte isola estritamente a barra de título da carta. O símbolo de custo de mana do lado direito costuma ser um problema (por exemplo, "2UU" sendo lido como "200"), mas o próximo passo do tratamento vai mitigar isso.

**5.2. Pré-processamento Específico para OCR** O Tesseract é extremamente sensível à resolução e ao contraste. A faixa de título recortada passará por um novo micro-pipeline de filtros:

1. **Upscaling:** Redimensionamento da faixa de título com um fator de escala (ex: `fx=3, fy=3`). O Tesseract exige que a altura dos caracteres tenha pelo menos \~30 pixels para uma leitura confiável.  
2. **Thresholding Agressivo (Binarização):** Conversão da imagem para Preto e Branco puro. Um *Adaptive Threshold* (ou de Otsu) será aplicado para transformar o fundo da barra de título em branco absoluto e as letras em preto absoluto.  
3. **Borrão Leve (Opcional):** Um leve *Gaussian Blur* antes da binarização para remover a granulação da impressão física da carta (os *halftone dots*), que o OCR costuma confundir com pontuação.

**5.3. Parametrização Otimizada do Tesseract** O Tesseract não deve operar em seu modo padrão. Ele será engessado através de *flags* de configuração (`config` string) para atuar de forma restrita e rápida:

* **Modo de Segmentação de Página (PSM):** Utilizaremos o `--psm 7` (Tratar a imagem como uma única linha de texto). Modos automáticos ou de bloco (como o `--psm 6`) tentam encontrar parágrafos e falham miseravelmente na barra de título.  
* **Modo de Engine (OEM):** Utilizaremos o `--oem 1` para acionar redes neurais LSTM, otimizadas para velocidade.  
* **Whitelist de Caracteres:** Para impedir que o OCR tente adivinhar símbolos bizarros, aplicamos uma restrição estrita de leitura (`tessedit_char_whitelist`). O OCR só poderá retornar letras maiúsculas/minúsculas, hífens, vírgulas e apóstrofos (caracteres presentes em nomes de cartas de MTG).

**5.4. Motor de Tolerância a Falhas (Fuzzy Matching)** A premissa do sistema é que **o OCR vai errar**. Ele pode ler "Kaalia of the Vast" como "Kaa1ia of the Vas".

* O texto "sujo" extraído pelo Tesseract é imediatamente injetado em um motor de comparação de strings (*RapidFuzz*, pela eficiência em C++).  
* O *RapidFuzz* compara a string suja contra a coluna `name` do banco de dados SQLite local, que contém os nomes oficiais únicos de todas as cartas do jogo.  
* O algoritmo calcula a distância de Levenshtein. Se a similaridade com um nome oficial for superior a um limite de confiança estabelecido (ex: `> 80%`), o sistema assume o nome oficial do banco de dados, corrigindo silenciosamente o erro do OCR.  
* É esse "Nome Oficial" limpo e validado que será passado para a etapa de verificação de Arte/Hash (definida na Parte 2\) para descobrir a edição exata.

### **Parte 6: Banco de Dados e Gerenciamento de Estado**

**6.1. O Banco de Dados Local (O Motor de Busca)**

A escolha tecnológica para o catálogo de cartas no dispositivo embarcado é o **SQLite3**.

* **Por que SQLite?** É um banco de dados relacional baseado em um único arquivo, extremamente leve, que não exige a execução de um serviço em segundo plano (como MySQL ou PostgreSQL) consumindo a preciosa RAM de 1GB do Orange Pi. A leitura é feita diretamente pelo script Python.

**6.2. Divisão de Estruturas (Catálogo vs. Coleção)**

O sistema deve isolar estritamente duas bases de dados distintas para evitar corrupção e lentidão:

1. **Catálogo (scryfall\_cache.db):** Banco de dados **somente leitura** no Orange Pi. Contém todas as cartas do jogo, suas impressões, e os hashes das artes.  
2. **Coleção (inventario.json):** Arquivo de **escrita**, onde o sistema registrará as cartas que passaram com sucesso pelo scanner.

**6.3. Otimização e Indexação (Obrigatório para Performance)**

Uma busca sequencial de texto em um banco com mais de 80.000 registros travaria o processamento de vídeo. Para que o *RapidFuzz* cruze o texto sujo do OCR com a base oficial em milissegundos, a estrutura do SQLite precisa de otimizações vitais:

* **Indexação Específica:** O banco deve ser criado já com um índice apontando para a coluna de nomes. O comando SQL CREATE INDEX idx\_card\_name ON cards(name); é fundamental. Isso transforma a busca de uma varredura linear lenta ($O(N)$) para uma busca em árvore hiper-rápida ($O(\\log N)$).  
* **Tabela de Hashes Relacional:** Uma segunda tabela no banco relacionará o Nome da Carta aos seus respectivos Hashes de Imagem (dHash). Assim, após o texto validar que a carta é um "Sol Ring", o banco devolve apenas os hashes daquelas impressões específicas.

**6.4. Geração e Atualização do Banco (A Função do PC Host)**

O microcomputador Orange Pi **nunca** deve construir esse banco do zero. O processamento pesado fica fora da caixa:

* Um script no PC do usuário faz o download do *Bulk Data* do Scryfall (um JSON gigante).  
* O PC processa as imagens, gera as matrizes de Hash, constrói o arquivo .db e aplica os índices.  
* O arquivo .db final (que deve ter apenas algumas dezenas de megabytes) é transferido via SSH/SFTP para o Orange Pi. O scanner apenas consome esse arquivo pronto.

**6.5. O Arquivo de Saída (Inventário)**

Para facilitar a exportação, integração com lojas (como a LigaMagic ou plataformas de venda) e garantir que os dados sejam legíveis, o resultado do scan será persistido no formato JSON.

* A estrutura de inserção no inventario.json deve incluir os metadados confirmados:  
* JSON

{  
  "nome": "Kaalia of the Vast",  
  "edicao": "Double Masters",  
  "scryfall\_id": "...",  
  "timestamp\_scan": "2026-05-26T10:33:00"  
}

*   
* **Gravação Assíncrona:** A função de salvar no JSON não deve bloquear a *thread* principal do vídeo. O frame atualiza, a validação ocorre, e a gravação do arquivo é despachada para segundo plano, permitindo que o usuário insira a próxima carta imediatamente.

### **Parte 7: Troubleshooting e Boas Práticas**

**7.1. O Problema da "Carta Fantasma" (Falsos Positivos no OCR)** Se o sistema estiver tentando registrar "cartas" que não existem (reflexos ou contornos errados):

* **Solução:** Implemente um teste de área mínima estrito. Se o `cv2.contourArea` for menor que um valor X (correspondente ao tamanho mínimo de uma carta na resolução da sua câmera), o sistema deve descartar o frame instantaneamente antes mesmo de passar pelo OCR.

**7.2. O Desafio das Cartas *Foil* e *Sleeves* (Manchas Brancas)** O maior inimigo da visão computacional em cartas de MTG são os "estouros de luz" (pixels saturados em branco puro) causados pelo reflexo do LED na superfície *Foil*.

* **Ajuste de Exposição:** Se o `cv2.threshold` estiver devolvendo uma imagem cheia de manchas brancas, não tente resolver apenas com código. Reduza a exposição da webcam (`v4l2-ctl -d /dev/video0 -c exposure_absolute=X`) até que o reflexo desapareça, mesmo que a imagem pareça levemente escura. O OCR prefere uma imagem escura com contraste alto a uma imagem estourada.

**7.3. Falha no *Perspective Transform* (Geometria Invertida)** Às vezes, a carta é detectada, mas o *warp* inverte a imagem (cabeça para baixo).

* **Solução:** O sistema deve verificar a orientação do texto. Após o OCR, se a confiança for muito baixa em todas as 4 orientações (0°, 90°, 180°, 270°), o sistema deve disparar um aviso de "Posicionamento Incorreto" em vez de tentar adivinhar a carta.

**7.4. Gestão de Memória no Orange Pi** O SQLite é leve, mas o carregamento do modelo do Tesseract e o buffer de frames do OpenCV podem consumir a RAM rapidamente.

* **Dica de Ouro:** Evite criar novos objetos de imagem dentro do loop `while` da câmera. Reaproveite os buffers de memória (ex: `img_proc = cv2.resize(...)` em vez de criar uma variável nova a cada 30ms) para evitar que o *Garbage Collector* do Python precise trabalhar excessivamente, o que causaria "travadinhas" no vídeo.

