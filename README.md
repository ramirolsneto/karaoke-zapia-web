# Karaokê Zapia — processamento automático no Kaggle GPU

Aplicação pessoal protegida por PIN. O site envia um link de compartilhamento `/dynps/share/` do MukaPlay e o tom escolhido para um kernel privado do Kaggle, consulta o estado do processamento e guarda o MP4 final em um Vercel Blob privado. O navegador recebe apenas uma URL de leitura temporária e assinada para o MP4.

## Configuração do deploy

- Importe este repositório privado no Vercel e publique a raiz do projeto.
- Configure `SITE_ACCESS_PIN`, `KAGGLE_USERNAME`, `KAGGLE_API_TOKEN` e conecte o store privado Vercel Blob `videoke-blob` (OIDC + `BLOB_STORE_ID`) ao projeto.
- Use Node.js 20 ou superior. `vercel.json` configura a função Python para incluir `KaraokeZapia_GPU_Kaggle.ipynb` e permite até 300 segundos por chamada.
- A função Python executa `kaggle kernels push/status/output` no servidor; nenhum PIN ou token Kaggle é enviado ao navegador.

## Utilização

1. Entre com o PIN configurado no Vercel.
2. Cole um link compartilhado MukaPlay HTTPS válido.
3. Confirme que tem autorização/direito para baixar, salvar e processar o conteúdo.
4. Escolha o tom (-6 a +6 semitons) e inicie o processamento. A tonalidade é aplicada na renderização do instrumental/MP4 no Kaggle.
5. Aguarde o status; o player abre o MP4 privado quando estiver pronto. O vídeo inclui controles nativos, botão para tela cheia e tentativa de reprodução remota quando o navegador/dispositivo oferece suporte.

O app processa somente após a confirmação explícita de direitos na interface. O fluxo depende da cota e disponibilidade de GPU do Kaggle, da página/arquivo de origem e dos limites de execução e armazenamento. A URL assinada do player expira após aproximadamente duas horas. A opção “Apagar MP4 privado” remove o arquivo do Blob.

## Arquivos principais

- `api/karaoke.py`: PIN, validação do link, envio/consulta do kernel, download do resultado e armazenamento privado.
- `api/media.js`: emite URL assinada e temporária para um único pathname privado.
- `KaraokeZapia_GPU_Kaggle.ipynb`: notebook template incluído no pacote da função e preenchido no servidor por execução.
- `index.html`: interface de PIN, envio, polling e reprodução.
