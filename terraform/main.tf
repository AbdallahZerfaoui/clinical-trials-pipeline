terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.34.0"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

#── Variables ────────────────────────────────────────────────────────────
variable "hcloud_token" {
  description = "Your Hetzner Cloud API token"
  type        = string
  sensitive   = true
}

variable "ssh_key_path" {
  description = "Path to your SSH public key"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

#── Load your SSH key so you can SSH into the server ────────────────────
locals {
  ssh_pub = file(var.ssh_key_path)
}

resource "hcloud_ssh_key" "default" {
  name       = "deploy-key"
  public_key = local.ssh_pub
}

#── Firewall: allow SSH, HTTP, HTTPS ────────────────────────────────────
resource "hcloud_firewall" "api_fw" {
  name         = "api-firewall"
  network_zone = "eu-central"

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}

#── Server: Ubuntu + cloud-init to install & run your API ─────────────────
resource "hcloud_server" "api" {
  name        = "clinical-trials-pipeline-server"
  server_type = "cx22"
  image       = "debian-12"
  location    = "nbg1"          # Nuremberg (eu‑central)
  ssh_keys    = [hcloud_ssh_key.default.name]
  firewall_ids = [hcloud_firewall.api_fw.id]

  user_data = <<-EOF
    #cloud-config
    runcmd:
      - apt-get update
      - DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip git
      - git clone https://github.com/AbdallahZerfaoui/ghr-serverless-etl.git /opt/api
      - pip3 install -r /opt/api/requirements.txt
      - cat << 'EOT' > /etc/systemd/system/api.service
        [Unit]
        Description=ClinicalTrials API
        After=network.target

        [Service]
        User=root
        WorkingDirectory=/opt/api
        ExecStart=/usr/bin/uvicorn main:app --host 0.0.0.0 --port 80
        Restart=always

        [Install]
        WantedBy=multi-user.target
        EOT
      - systemctl daemon-reload
      - systemctl enable api.service
      - systemctl start api.service
  EOF
}

#── Output the public IP so you can test your API ────────────────────────
output "api_server_ip" {
  description = "IP address of the newly created API server"
  value       = hcloud_server.api.ipv4_address
}
