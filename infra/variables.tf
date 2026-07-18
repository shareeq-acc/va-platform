variable "contabo_client_id" {
  type        = string
  description = "Contabo API Client ID"
  sensitive   = true
}

variable "contabo_client_secret" {
  type        = string
  description = "Contabo API Client Secret"
  sensitive   = true
}

variable "contabo_username" {
  type        = string
  description = "Contabo CCP API Username"
}

variable "contabo_password" {
  type        = string
  description = "Contabo CCP API Password"
  sensitive   = true
}

variable "namecheap_username" {
  type        = string
  description = "Namecheap Account Username"
}

variable "namecheap_api_key" {
  type        = string
  description = "Namecheap API Key"
  sensitive   = true
}

variable "namecheap_client_ip" {
  type        = string
  description = "Your whitelisted IP for Namecheap API calls"
}

variable "root_domain" {
  type        = string
  description = "Root domain managed under Namecheap (e.g. mydomain.com)"
}

variable "staging_subdomain" {
  type        = string
  description = "Hostname for staging environment (e.g. staging)"
  default     = "staging"
}

variable "production_ip" {
  type        = string
  description = "IP address of the hand-provisioned production VPS"
}

variable "ssh_public_key" {
  type        = string
  description = "Public SSH key to upload and authorize on the VPS"
}

variable "contabo_region" {
  type        = string
  description = "Contabo Region (e.g., EU, US-central, US-east)"
  default     = "EU"
}

variable "contabo_product_id" {
  type        = string
  description = "Contabo product ID for the VPS plan (e.g., V92)"
  default     = "V92"
}

variable "contabo_image_id" {
  type        = string
  description = "Contabo OS Image ID (typically corresponding to Ubuntu 22.04 LTS)"
  default     = "ubuntu-22.04-image-id" # Placeholder or retrieved image ID
}
