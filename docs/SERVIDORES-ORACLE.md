# Criar servidores na Oracle Cloud (grátis)

A Oracle Cloud tem máquinas **"Always Free"**, gratuitas para sempre. Com isso o Asafe
consegue **criar servidores sozinho**, sem custo.

> Tempo estimado: 20–30 minutos, uma vez só. A Oracle pede cartão no cadastro
> (só para verificação); as máquinas "Always Free" não são cobradas.

## 1. Criar a conta
1. Acesse <https://www.oracle.com/cloud/free/> e crie a conta.
2. Escolha a **região** mais próxima (ex.: *Brazil East – São Paulo*). Ela não pode ser trocada depois.

## 2. Criar a rede (uma vez)
1. Menu ☰ → **Networking → Virtual cloud networks → Start VCN Wizard → Create VCN with Internet Connectivity**.
2. Dê um nome (ex.: `asafe-rede`) e confirme.
3. Abra a VCN criada → **Subnets** → copie o **OCID da sub-rede pública** → `OCI_SUBNET_ID`.

## 3. Pegar os outros identificadores
| Variável | Onde achar |
|---|---|
| `OCI_COMPARTMENT_ID` | ☰ → **Identity → Compartments** → OCID do compartimento (pode ser o *root*) |
| `OCI_AVAILABILITY_DOMAIN` | ☰ → **Compute → Instances → Create instance** → nome do *Availability domain* (ex.: `abcd:SA-SAOPAULO-1-AD-1`) |
| `OCI_IMAGE_ID` | ☰ → **Compute → Images** → *Oracle Linux 9* ou *Ubuntu 22.04* → OCID (da sua região) |
| `OCI_SHAPE` | Padrão `VM.Standard.E2.1.Micro` (grátis). Alternativa grátis: `VM.Standard.A1.Flex` |

## 4. Chave de acesso da API
1. Clique no seu perfil (canto superior direito) → **My profile → API keys → Add API key**.
2. Baixe a chave privada e copie o trecho de configuração mostrado.
3. Na máquina do Asafe, salve:
   - o trecho em `~/.oci/config`
   - a chave privada no caminho indicado em `key_file`

## 5. Ligar no Asafe
```bash
pip install oci
export OCI_COMPARTMENT_ID=ocid1.compartment...
export OCI_SUBNET_ID=ocid1.subnet...
export OCI_IMAGE_ID=ocid1.image...
export OCI_AVAILABILITY_DOMAIN="abcd:SA-SAOPAULO-1-AD-1"
export ASAFE_URL_PUBLICA=https://endereco-publico-do-asafe   # a máquina nova precisa alcançar o Asafe
ASAFE_ADMIN_TOKEN=... python -m asafe
```

No painel: **Servidores → Gerar servidor → Criar máquina nova → Oracle Cloud**. Em 2–5 minutos
a máquina passa de **Criando** para **Ao vivo**.

## Problemas comuns
- **"Out of host capacity"**: a Oracle está sem máquinas grátis naquela região no momento. Tente mais tarde
  ou use `OCI_SHAPE=VM.Standard.A1.Flex`.
- **Fica em "Criando" para sempre**: a máquina não alcança o Asafe. Confira `ASAFE_URL_PUBLICA` e se
  a porta do Asafe está aberta para a internet.
- **Limite grátis**: até 2 máquinas `E2.1.Micro` (ou 4 núcleos/24 GB em `A1.Flex`) por conta.
