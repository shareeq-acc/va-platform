terraform {
  required_version = ">= 1.0.0"
  required_providers {
    contabo = {
      source  = "contabo/contabo"
      version = ">= 0.1.43"
    }
    namecheap = {
      source  = "namecheap/namecheap"
      version = ">= 2.0.0"
    }
  }
}

provider "contabo" {
  oauth2_client_id     = var.contabo_client_id
  oauth2_client_secret = var.contabo_client_secret
  oauth2_user          = var.contabo_username
  oauth2_pass          = var.contabo_password
}

provider "namecheap" {
  user_name   = var.namecheap_username
  api_user    = var.namecheap_username
  api_key     = var.namecheap_api_key
  client_ip   = var.namecheap_client_ip
  use_sandbox = false
}
