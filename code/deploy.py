import socket
import subprocess

import sys

from common import *
import etcd

clusterdata_dir = "/endpoint/etcd-clusterdata/"
apiserver_dir = "/endpoint/apiserver/"
# apiserver_secure_dir = "/endpoint/apiserver-secure/"
hostname = socket.gethostname()


#
# port_cluster_data = 0
# port_apiserver = 0
# port_apiserver_secure = 0

def deploy_loadbalancer():
    print("Deploying wharf proxy service")

    check_cmd = "docker ps|grep wharf-proxy"
    rm_cmd = "docker rm -f wharf-proxy"

    start_cmd = "docker run -d --name wharf-proxy \
                    --net=host --privileged --restart=on-failure \
                    wharf-proxy:0.1 --debug=true"

    try:
        check_result = shell_exec(check_cmd)
    except subprocess.CalledProcessError as e:
        print("---No existing container,starting a new one---")
        check_result = False
    if check_result:
        shell_exec(rm_cmd)

    shell_exec(start_cmd)


def deploy_etcd_metadata():
    print("Deploying wharf metadata service")
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

    check_times = 50
    while check_times:
        try:
            client = etcd.Client(port=2379)
            client.set("/init", "", ttl=10)
        except etcd.EtcdConnectionFailed as e:
            print("...Waiting to get ready...")
            check_times = check_times - 1
            continue
        break

    if not check_times:
        print("Failed to deploy etcd metadata service...Exiting")
        sys.exit(1)


def init_etcd_metadata(advertise_address):
    print("Initializing metadata...")
    meta_client = etcd.Client(host="127.0.0.1", port=2379)

    # hostname = socket.gethostname()
    port_cluster_data = str(get_idle_port(advertise_address))
    port_apiserver = str(get_idle_port(advertise_address))
    port_apiserver_secure = str(get_idle_port(advertise_address))

    # port_cluster_data = "12379"
    # port_apiserver= "18080"
    # port_apiserver_secure = "6443"

    meta_client.set(key=clusterdata_dir + hostname + "/name", value=hostname)
    meta_client.set(key=clusterdata_dir + hostname + "/address", value=advertise_address)
    meta_client.set(key=clusterdata_dir + hostname + "/port", value=port_cluster_data)

    meta_client.set(key=apiserver_dir + hostname + "/name", value=hostname)
    meta_client.set(key=apiserver_dir + hostname + "/address", value=advertise_address)
    meta_client.set(key=apiserver_dir + hostname + "/port", value=port_apiserver)
    meta_client.set(key=apiserver_dir + hostname + "/secure_port", value=port_apiserver_secure)

    # meta_client.set(key=apiserver_secure_dir + hostname + "/name", value=hostname)
    # meta_client.set(key=apiserver_secure_dir + hostname + "/address",
    #                 value=advertise_address)
    # meta_client.set(key=apiserver_secure_dir + hostname + "/port",
    #                 value=port_apiserver_secure)


def deploy_etcd_cluster():
    print("Deploying wharf cluster datastore service")
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
        # if "Connection refused" in discovery:
        #     continue
        if key in discovery:
            break
        timeout -= 1

    if not timeout:
        print("Failed to acquire etcd discovery token")
        return

    discovery_http = "http://127.0.0.1:2379/v2/keys/discovery/{key}".format(key=key)
    # advertise_address = os.environ["ADVERTISE_ADDRESS"]
    etcd_client = etcd.Client(port=2379)
    advertise_address = etcd_client.get(key=clusterdata_dir + hostname + "/address").value
    advertise_port = etcd_client.get(key=clusterdata_dir + hostname + "/port").value
    advertise_url = "https://{address}:{port}".format(address=advertise_address,port=advertise_port)

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
                  --listen-client-urls={advertise_url} \
                  --advertise-client-urls={advertise_url} \
                  --discovery={discovery} \
                  --data-dir=/var/lib/etcd-wharf-meta".format(name=advertise_address,
                                                              advertise_address=advertise_address,
                                                              advertise_url=advertise_url,
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
    print("Deploying wharf cluster apiserver service")

    try:
        check_filepath("/etc/wharf/auth/kubernetes.pem")
        check_filepath("/etc/wharf/auth/kubernetes-key.pem")
        check_filepath("/etc/wharf/auth/ca.pem")
    except FileNotFoundException as e:
        print(e.message)
        return

    # advertise_address = os.environ["ADVERTISE_ADDRESS"]
    etcd_client = etcd.Client(port=2379)
    advertise_address = etcd_client.get(key=apiserver_dir + hostname + "/address").value
    port = etcd_client.get(key=apiserver_dir + hostname + "/port").value
    secure_port = etcd_client.get(key=apiserver_dir + hostname + "/secure_port").value

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
                  --secure-port={secure_port} \
                  --insecure-bind-address={advertise_address} \
                  --insecure-port={port} \
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
                  --etcd-servers=https://{advertise_address}:12379 \
                  --enable-swagger-ui=true \
                  --allow-privileged=true \
                  --apiserver-count=3 \
                  --audit-log-maxage=30 \
                  --audit-log-maxbackup=3 \
                  --audit-log-maxsize=100 \
                  --audit-log-path=/var/lib/wharf/kubernetes/audit.log \
                  --event-ttl=1h \
                  --v=2".format(advertise_address=advertise_address, port=port,
                                secure_port=secure_port)

    try:
        check_result = shell_exec(container_check_cmd)
    except subprocess.CalledProcessError as e:
        print("---No existing container,starting a new one---")
        check_result = False
    if check_result:
        shell_exec(container_rm_cmd)

    shell_exec(start_cmd)


def deploy_cmanager():
    print("Deploying wharf cluster cmanager service")
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
                  --master=http://{advertise_address}:18080 \
                  --service-cluster-ip-range=10.254.0.0/16 \
                  --cluster-name=wharf \
                  --cluster-signing-cert-file=/etc/wharf/auth/ca.pem \
                  --cluster-signing-key-file=/etc/wharf/auth/ca-key.pem \
                  --service-account-private-key-file=/etc/wharf/auth/ca-key.pem \
                  --root-ca-file=/etc/wharf/auth/ca.pem \
                  --leader-elect=true \
                  --v=4 \
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
    print("Deploying wharf cluster scheduler service")
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
                      --master=http://{advertise_address}:18080 \
                      --leader-elect=true \
                      --v=2".format(advertise_address=advertise_address)

    try:
        check_result = shell_exec(container_check_cmd)
    except subprocess.CalledProcessError as e:
        check_result = False
    if check_result:
        shell_exec(container_rm_cmd)

    shell_exec(start_cmd)
