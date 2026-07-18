resource "contabo_secret" "ssh_key" {
  name  = "vapi-platform-ssh-key"
  type  = "ssh"
  value = var.ssh_public_key
}

resource "contabo_instance" "staging" {
  display_name = "vapi-platform-staging"
  product_id   = var.contabo_product_id
  region       = var.contabo_region
  image_id     = var.contabo_image_id
  default_user = "root"
  ssh_keys     = [contabo_secret.ssh_key.id]

  # User data to bootstrap the staging instance with Docker & Git
  user_data    = <<-EOF
    #!/bin/bash
    apt-get update
    apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release git

    # Install Docker & Docker Compose
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    
    # Prepare deploy target directory
    mkdir -p /opt/va-platform
    EOF
}

resource "namecheap_domain_records" "dns" {
  domain = var.root_domain
  mode   = "MERGE"

  # Staging subdomain mapping
  record {
    hostname = var.staging_subdomain
    type     = "A"
    address  = contabo_instance.staging.ip_config[0].v4[0].ip
    ttl      = 600
  }

  # Production subdomain mapping
  record {
    hostname = "app"
    type     = "A"
    address  = var.production_ip
    ttl      = 600
  }
}
