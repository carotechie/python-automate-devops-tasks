#!/usr/bin/env python3
"""Crea instancias EC2 de ejemplo en LocalStack para practicar.

Solo funciona contra un endpoint local: se niega a correr contra AWS real
para que no generes costos por accidente.
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError

LOCAL_HOSTS = {"localhost", "127.0.0.1", "localstack", "host.docker.internal", "::1"}

# Datos ficticios, como en la diapositiva 06: staging en 3 regiones (una detenida).
SAMPLE_INSTANCES = [
    {"region": "us-east-1", "name": "web-staging-01", "env": "staging", "type": "t3.micro"},
    {"region": "eu-west-1", "name": "api-staging-01", "env": "staging", "type": "t3.small", "stopped": True},
    {"region": "sa-east-1", "name": "worker-staging-01", "env": "staging", "type": "t3.micro"},
]
FAKE_AMI = "ami-0abcdef1234567890"


def is_local_endpoint(url: str) -> bool:
    return (urlparse(url).hostname or "") in LOCAL_HOSTS


def existing_names(ec2) -> set[str]:
    names = set()
    paginator = ec2.get_paginator("describe_instances")
    filters = [{"Name": "tag:lab", "Values": ["python-automatiza-devops"]}]
    for page in paginator.paginate(Filters=filters):
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                if instance["State"]["Name"] == "terminated":
                    continue
                tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
                names.add(tags.get("Name", ""))
    return names


def create_instance(ec2, spec: dict) -> str:
    tags = [
        {"Key": "Name", "Value": spec["name"]},
        {"Key": "env", "Value": spec["env"]},
        {"Key": "owner", "Value": "pyladies-demo"},
        {"Key": "lab", "Value": "python-automatiza-devops"},
    ]
    response = ec2.run_instances(
        ImageId=FAKE_AMI,
        InstanceType=spec["type"],
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{"ResourceType": "instance", "Tags": tags}],
    )
    instance_id = response["Instances"][0]["InstanceId"]
    if spec.get("stopped"):
        ec2.stop_instances(InstanceIds=[instance_id])
    return instance_id


def seed(endpoint_url: str) -> int:
    created = 0
    for spec in SAMPLE_INSTANCES:
        ec2 = boto3.client("ec2", region_name=spec["region"], endpoint_url=endpoint_url)
        if spec["name"] in existing_names(ec2):
            print(f"= {spec['name']} ya existe en {spec['region']}")
            continue
        instance_id = create_instance(ec2, spec)
        created += 1
        print(f"+ {spec['name']} ({instance_id}) en {spec['region']} con env={spec['env']}")
    return created


class SpanishHelpFormatter(argparse.HelpFormatter):
    """Muestra 'uso:' en lugar de 'usage:' en la ayuda."""

    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, prefix or "uso: ")


def new_parser(**kwargs) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(formatter_class=SpanishHelpFormatter, add_help=False, **kwargs)
    parser._optionals.title = "opciones"
    parser.add_argument("-h", "--help", action="help", help="Muestra esta ayuda y termina.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = new_parser(description="Crea instancias EC2 de ejemplo en LocalStack.")
    parser.add_argument(
        "--endpoint-url",
        default=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
        help="Endpoint de LocalStack (por defecto: http://localhost:4566).",
    )
    args = parser.parse_args(argv)

    if not is_local_endpoint(args.endpoint_url):
        print(f"Error: {args.endpoint_url} no parece local. Este script solo corre contra LocalStack.", file=sys.stderr)
        return 1

    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    try:
        created = seed(args.endpoint_url)
    except (ClientError, BotoCoreError) as exc:
        print(f"Error: no se pudo sembrar LocalStack ({exc}). ¿Está corriendo? Prueba: make lab-up", file=sys.stderr)
        return 1
    print(f"Listo: {created} instancia(s) nuevas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
