output "staging_vps_ip" {
  value       = contabo_instance.staging.ip_config[0].v4[0].ip
  description = "The public IPv4 address of the staging VPS"
}

output "staging_url" {
  value       = "https://${var.staging_subdomain}.${var.root_domain}"
  description = "The URL of the staging web application"
}

output "production_url" {
  value       = "https://app.${var.root_domain}"
  description = "The URL of the production web application"
}
