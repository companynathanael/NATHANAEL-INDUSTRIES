"""Provedor Oracle Cloud (OCI). A Oracle tem máquinas "Always Free" (grátis para sempre).

Requer:  pip install oci
Configuração (variáveis de ambiente):
  OCI_CONFIG_FILE          arquivo de credenciais da OCI (padrão ~/.oci/config)
  OCI_PERFIL               perfil dentro do arquivo (padrão DEFAULT)
  OCI_COMPARTMENT_ID       compartimento onde criar as máquinas
  OCI_SUBNET_ID            sub-rede (com IP público, para a máquina alcançar o Asafe)
  OCI_IMAGE_ID             imagem (ex.: Oracle Linux ou Ubuntu)
  OCI_AVAILABILITY_DOMAIN  domínio de disponibilidade (ex.: "abcd:SA-SAOPAULO-1-AD-1")
  OCI_SHAPE                padrão "VM.Standard.E2.1.Micro" (gratuita)
  OCI_SSH_PUBLIC_KEY       opcional: chave SSH para acessar a máquina
"""

import base64
import os

from . import ErroProvedor, Maquina, Pedido, Provedor, script_inicial

OBRIGATORIAS = ("OCI_COMPARTMENT_ID", "OCI_SUBNET_ID", "OCI_IMAGE_ID", "OCI_AVAILABILITY_DOMAIN")
ESTADOS = {"PROVISIONING": "criando", "STARTING": "criando", "RUNNING": "rodando", "STOPPING": "parada",
           "STOPPED": "parada", "TERMINATING": "destruida", "TERMINATED": "destruida"}


class ProvedorOracle(Provedor):
    nome = "oracle"
    descricao = "Oracle Cloud (tem máquinas gratuitas)"

    def __init__(self):
        self._cliente = None

    def _oci(self):
        import oci  # dependência opcional
        return oci

    def configurado(self):
        try:
            self._oci()
        except ImportError:
            return False, "Instale o SDK da Oracle: pip install oci"
        faltando = [v for v in OBRIGATORIAS if not os.environ.get(v)]
        if faltando:
            return False, "Faltam variáveis: " + ", ".join(faltando)
        return True, ""

    def _compute(self):
        if self._cliente is None:
            oci = self._oci()
            config = oci.config.from_file(os.environ.get("OCI_CONFIG_FILE", "~/.oci/config"),
                                          os.environ.get("OCI_PERFIL", "DEFAULT"))
            self._cliente = oci.core.ComputeClient(config)
        return self._cliente

    def criar(self, pedido: Pedido) -> Maquina:
        ok, motivo = self.configurado()
        if not ok:
            raise ErroProvedor(motivo)
        oci = self._oci()
        m = oci.core.models
        shape = pedido.opcoes.get("shape") or os.environ.get("OCI_SHAPE", "VM.Standard.E2.1.Micro")
        metadata = {"user_data": base64.b64encode(script_inicial(pedido).encode()).decode()}
        if os.environ.get("OCI_SSH_PUBLIC_KEY"):
            metadata["ssh_authorized_keys"] = os.environ["OCI_SSH_PUBLIC_KEY"]
        detalhes = m.LaunchInstanceDetails(
            display_name=f"asafe-{pedido.nome}",
            compartment_id=os.environ["OCI_COMPARTMENT_ID"],
            availability_domain=os.environ["OCI_AVAILABILITY_DOMAIN"],
            shape=shape,
            source_details=m.InstanceSourceViaImageDetails(image_id=os.environ["OCI_IMAGE_ID"]),
            create_vnic_details=m.CreateVnicDetails(subnet_id=os.environ["OCI_SUBNET_ID"], assign_public_ip=True),
            metadata=metadata,
            freeform_tags={"criado_por": "asafe", "servidor": pedido.nome},
        )
        if shape.endswith(".Flex"):
            detalhes.shape_config = m.LaunchInstanceShapeConfigDetails(
                ocpus=float(pedido.opcoes.get("ocpus", 1)), memory_in_gbs=float(pedido.opcoes.get("memoria_gb", 6)))
        try:
            inst = self._compute().launch_instance(detalhes).data
        except Exception as e:  # erros da OCI (cota, permissão, sem capacidade...)
            raise ErroProvedor(f"Oracle recusou a criação: {getattr(e, 'message', e)}") from e
        return Maquina(id=inst.id, estado=ESTADOS.get(inst.lifecycle_state, "criando"),
                       detalhes={"shape": shape, "regiao": os.environ["OCI_AVAILABILITY_DOMAIN"]})

    def destruir(self, maquina_id: str) -> None:
        try:
            self._compute().terminate_instance(maquina_id)
        except Exception as e:
            raise ErroProvedor(f"Oracle recusou a remoção: {getattr(e, 'message', e)}") from e

    def estado(self, maquina_id: str) -> Maquina:
        inst = self._compute().get_instance(maquina_id).data
        return Maquina(id=maquina_id, estado=ESTADOS.get(inst.lifecycle_state, "erro"))
