import subprocess
from common import *


def deploy_loadbalancer():
    pass


def deploy_etcd_metadata():
    timeout = 10
    while timeout:
        discovery = shell_exec("curl -s https://discovery.etcd.io/new?size=1")
        if "etcd.io" in discovery:
            break
        timeout -= 1

    if "etcd.io" in discovery:
        discovery_http = discovery.replace("https", "http")

    check_cmd = "docker ps|grep wharf-meta-etcd"
    rm_cmd = "docker rm -f wharf-meta-etcd"

    start_cmd = "docker run -d --name wharf-meta-etcd \
                    -v /var/lib/wharf/metadata:/var/lib/wharf/metadata \
                  --net=host --privileged --restart=on-failure \
                    gcr.io/google-containers/etcd:3.1.11 etcd \
                  --name=wharf-meta \
                  --initial-advertise-peer-urls=http://127.0.0.1:2380 \
                  --listen-peer-urls=http://127.0.0.1:2380 \
                  --listen-client-urls=http://127.0.0.1:2379 \
                  --advertise-client-urls=http://127.0.0.1:2379 \
                  --discovery={discovery} \
                  --data-dir=/var/lib/etcd-wharf-meta".format(discovery=discovery_http)

    try:
        check_result = shell_exec(check_cmd)
    except subprocess.CalledProcessError as e:
        print("---No existing container,starting a new one---")
        check_result = False
    if check_result:
        shell_exec(rm_cmd)

    shell_exec(start_cmd)


def deploy_etcd_cluster():
    try:
        check_filepath("/etc/wharf/auth/etcd.pem")
        check_filepath("/etc/wharf/auth/etcd-key.pem")
        check_filepath("/etc/wharf/auth/ca.pem")
    except FileNotFoundException as e:
        print(e.message)
        return

    timeout = 10
    key = shell_exec("head -c 16 /dev/urandom | od -An -t x | tr -d ' '").replace("\n", "")
    while timeout:
        discovery = shell_exec(
            "curl -X PUT http://127.0.0.1:2379/v2/keys/discovery/{key}/_config/size -d value=1".format(key=key))
        if key in discovery:
            break
        timeout -= 1

    if not timeout:
        print("Failed to acquire etcd discovery token")
        return

    discovery_http = "http://127.0.0.1:2379/v2/keys/discovery/{key}".format(key=key)
    advertise_address = os.environ["ADVERTISE_ADDRESS"]
    container_check_cmd = "docker ps|grep wharf-cluster-etcd"
    container_rm_cmd = "docker rm -f wharf-cluster-etcd"

    start_cmd = "docker run -d --name wharf-cluster-etcd \
                    -v /var/lib/wharf/clusterdata:/var/lib/wharf/clusterdata \
                    -v /etc/wharf/:/etc/wharf/ \
                  --net=host --privileged --restart=on-failure \
                    gcr.io/google-containers/etcd:3.1.11 etcd \
                  --name={name} \
                  --cert-file=/etc/wharf/auth/etcd.pem \
                  --key-file=/etc/wharf/auth/etcd-key.pem \
                  --peer-cert-file=/etc/wharf/auth/etcd.pem \
                  --peer-key-file=/etc/wharf/auth/etcd-key.pem \
                  --trusted-ca-file=/etc/wharf/auth/ca.pem \
                  --peer-trusted-ca-file=/etc/wharf/auth/ca.pem \
                  --initial-advertise-peer-urls=https://{advertise_address}:3380 \
                  --listen-peer-urls=https://{advertise_address}:3380 \
                  --listen-client-urls=https://{advertise_address}:3379 \
                  --advertise-client-urls=https://{advertise_address}:3379 \
                  --discovery={discovery} \
                  --data-dir=/var/lib/etcd-wharf-meta".format(name=advertise_address,
                                                              advertise_address=advertise_address,
                                                              discovery=discovery_http)

    try:
        check_result = shell_exec(container_check_cmd)
    except subprocess.CalledProcessError as e:
        print("---No existing container,starting a new one---")
        check_result = False
    if check_result:
        shell_exec(container_rm_cmd)

    shell_exec(start_cmd)


def deploy_apiserver():
    try:
        check_filepath("/etc/wharf/auth/kubernetes.pem")
        check_filepath("/etc/wharf/auth/kubernetes-key.pem")
        check_filepath("/etc/wharf/auth/ca.pem")
    except FileNotFoundException as e:
        print(e.message)
        return

    advertise_address = os.environ["ADVERTISE_ADDRESS"]

    container_check_cmd = "docker ps|grep wharf-apiserver"

    container_rm_cmd = "docker rm -f wharf-apiserver"

    start_cmd = "docker run -ti -d --name wharf-apiserver \
                --restart=on-failure \
                -v /etc/wharf/:/etc/wharf/ \
                -v /var/lib/wharf/kubernetes/:/var/lib/wharf/kubernetes/ \
                -v /etc/localtime:/etc/localtime:ro \
                 --net=host \
                 --privileged \
                 cnetes:0.1 \
                 kube-apiserver \
                 --admission-control=NamespaceLifecycle,LimitRanger,ServiceAccount,DefaultStorageClass,ResourceQuota \
                  --advertise-address={advertise_address} \
                  --bind-address={advertise_address} \
                  --insecure-bind-address={advertise_address} \
                  --authorization-mode=RBAC \
                  --kubelet-https=true \
                  --service-cluster-ip-range=10.254.0.0/16 \
                  --service-node-port-range=30000-40000 \
                  --tls-cert-file=/etc/wharf/auth/kubernetes.pem \
                  --tls-private-key-file=/etc/wharf/auth/kubernetes-key.pem \
                  --client-ca-file=/etc/wharf/auth/ca.pem \
                  --service-account-key-file=/etc/wharf/auth/ca-key.pem \
                  --etcd-cafile=/etc/wharf/auth/ca.pem \
                  --etcd-certfile=/etc/wharf/auth/etcd.pem \
                  --etcd-keyfile=/etc/wharf/auth/etcd-key.pem \
                  --etcd-servers=https://{advertise_address}:3379 \
                  --enable-swagger-ui=true \
                  --allow-privileged=true \
                  --apiserver-count=3 \
                  --audit-log-maxage=30 \
                  --audit-log-maxbackup=3 \
                  --audit-log-maxsize=100 \
                  --audit-log-path=/var/lib/wharf/kubernetes/audit.log \
                  --event-ttl=1h \
                  --v=2".format(advertise_address=advertise_address)

    try:
        check_result = shell_exec(container_check_cmd)
    except subprocess.CalledProcessError as e:
        print("---No existing container,starting a new one---")
        check_result = False
    if check_result:
        shell_exec(container_rm_cmd)

    shell_exec(start_cmd)


def deploy_cmanager():
    advertise_address = os.environ["ADVERTISE_ADDRESS"]
    container_check_cmd = "docker ps|grep wharf-cmanager"
    container_rm_cmd = "docker rm -f wharf-cmanager"

    start_cmd = "docker run -ti   \
                -d  --restart=on-failure --name wharf-cmanager \
                -v /etc/wharf/:/etc/wharf/ \
                -v /var/lib/wharf/kubernetes/:/var/lib/wharf/kubernetes/ \
                -v /etc/localtime:/etc/localtime:ro \
                 --net=host \
                 --privileged \
                 cnetes:0.1 \
                 kube-controller-manager \
                  --address=127.0.0.1 \
                  --master=http://{advertise_address}:8080 \
                  --service-cluster-ip-range=10.254.0.0/16 \
                  --cluster-name=wharf \
                  --cluster-signing-cert-file=/etc/wharf/auth/ca.pem \
                  --cluster-signing-key-file=/etc/wharf/auth/ca-key.pem \
                  --service-account-private-key-file=/etc/wharf/auth/ca-key.pem \
                  --root-ca-file=/etc/wharf/auth/ca.pem \
                  --leader-elect=true \
                  --v=2 \
                   --allocate-node-cidrs=false".format(advertise_address=advertise_address)

    try:
        check_result = shell_exec(container_check_cmd)
    except subprocess.CalledProcessError as e:
        print("---No existing container,starting a new one---")
        check_result = False
    if check_result:
        shell_exec(container_rm_cmd)

    shell_exec(start_cmd)


def deploy_scheduler():
    advertise_address = os.environ["ADVERTISE_ADDRESS"]
    container_check_cmd = "docker ps|grep wharf-scheduler"
    container_rm_cmd = "docker rm -f wharf-scheduler"

    start_cmd = "docker run -ti   \
                -d  --restart=on-failure --name wharf-scheduler \
                -v /etc/wharf/:/etc/wharf/ \
                -v /etc/localtime:/etc/localtime:ro \
                 --net=host \
                 --privileged \
                 cnetes:0.1 \
                 kube-scheduler \
                    --address=127.0.0.1 \
                      --master=http://{advertise_address}:8080 \
                      --leader-elect=true \
                      --v=2".format(advertise_address=advertise_address)

    try:
        check_result = shell_exec(container_check_cmd)
    except subprocess.CalledProcessError as e:
        check_result = False
    if check_result:
        shell_exec(container_rm_cmd)

    shell_exec(start_cmd)
