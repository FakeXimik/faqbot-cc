terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" {}
variable "language_endpoint" {}
variable "language_key" { sensitive = true }

import {
  to = azurerm_resource_group.rg
  id = "/subscriptions/${var.subscription_id}/resourceGroups/rg-faqbot"
}
import {
  to = azurerm_service_plan.plan
  id = "/subscriptions/${var.subscription_id}/resourceGroups/rg-faqbot/providers/Microsoft.Web/serverFarms/plan-faqbot"
}
import {
  to = azurerm_linux_web_app.app
  id = "/subscriptions/${var.subscription_id}/resourceGroups/rg-faqbot/providers/Microsoft.Web/sites/faqbot-web-cc"
}


resource "azurerm_resource_group" "rg" {
  name     = "rg-faqbot"
  location = "northeurope"
}


resource "azurerm_service_plan" "plan" {
  name                = "plan-faqbot"
  resource_group_name = azurerm_resource_group.rg.name
  location            = "spaincentral"
  os_type             = "Linux"
  sku_name            = "F1"
}

resource "azurerm_linux_web_app" "app" {
  name                = "faqbot-web-cc"
  resource_group_name = azurerm_resource_group.rg.name
  location            = "spaincentral"
  service_plan_id     = azurerm_service_plan.plan.id
  https_only          = true

  site_config {
    always_on           = false
    minimum_tls_version = "1.2"
    ftps_state          = "Disabled"
    application_stack { python_version = "3.12" }
  }

  app_settings = {
    AZURE_LANGUAGE_ENDPOINT       	= var.language_endpoint
    AZURE_LANGUAGE_KEY             	= var.language_key
    CQA_PROJECT_NAME               	= "cloud-computing-faq"
    CQA_DEPLOYMENT_NAME            	= "production"
    CONFIDENCE_THRESHOLD           	= "0.25"
    SCM_DO_BUILD_DURING_DEPLOYMENT 	= "true"

  }
}