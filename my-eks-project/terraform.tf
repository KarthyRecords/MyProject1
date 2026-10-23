terraform {
  backend "s3" {
    bucket         = "teracotta-terraform-state"
    key            = "vpc/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "teracotta-terraform-locks"
  }
}

