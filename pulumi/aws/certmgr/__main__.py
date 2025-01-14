import os

import pulumi
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm
from pulumi_kubernetes.helm.v3 import FetchOpts

from kic_util import pulumi_config


# Removes the status field from the Nginx Ingress Helm Chart, so that i#t is
# compatible with the Pulumi Chart implementation.
def remove_status_field(obj):
    if obj['kind'] == 'CustomResourceDefinition' and 'status' in obj:
        del obj['status']


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

eks_project_name = project_name_from_project_dir('eks')
eks_stack_ref_id = f"{pulumi_user}/{eks_project_name}/{stack_name}"
eks_stack_ref = pulumi.StackReference(eks_stack_ref_id)
kubeconfig = eks_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

k8s_provider = k8s.Provider(resource_name=f'ingress-setup-sample',
                            kubeconfig=kubeconfig)

ns = k8s.core.v1.Namespace(resource_name='cert-manager',
                           metadata={'name': 'cert-manager'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

chart_values = {
    "installCRDs": True
}
helm_repo_name = 'jetstack'
helm_repo_url = 'https://charts.jetstack.io'

config = pulumi.Config('certmgr')
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = 'v1.4.0'
helm_repo_name = config.get('certmgr_helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'jetstack'

helm_repo_url = config.get('certmgr_helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://charts.jetstack.io'

chart_ops = helm.ChartOpts(
    chart='cert-manager',
    namespace=ns.metadata.name,
    repo=helm_repo_name,
    fetch_opts=FetchOpts(repo=helm_repo_url),
    version=chart_version,
    values=chart_values,
    transformations=[remove_status_field],
)

certmgr_chart = helm.Chart(release_name='certmgr',
                           config=chart_ops,
                           opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[ns]))
