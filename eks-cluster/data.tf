data "aws_vpc" "main" {
  filter {
    name   = "tag:Name"
    values = ["k-vpc"]
  }
}

data "aws_subnet" "subnet1" {
  filter {
    name   = "tag:Name"
    values = ["k-subnet1"]
  }
}

data "aws_subnet" "subnet2" {
  filter {
    name   = "tag:Name"
    values = ["k-subnet2"]
  }
}

data "aws_ssm_parameter" "github_token" {
  name = "/github/eks/token"
}