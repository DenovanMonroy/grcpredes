#!/bin/bash

# Script de configuración para el sistema de transferencia de archivos

echo "=== Configurando entorno para transferencia de archivos gRPC ==="

# Actualizar sistema
sudo apt update

# Instalar Python y pip si no están instalados
sudo apt install -y python3 python3-pip python3-venv

# Crear entorno virtual
python3 -m venv grpc_env
source grpc_env/bin/activate

# Instalar dependencias
pip install grpcio grpcio-tools

# Generar archivos Python desde el .proto
echo "Generando archivos gRPC..."
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. file_transfer.proto

echo "✅ Configuración completada"
echo ""
echo "Para usar el sistema:"
echo "1. Activar entorno: source grpc_env/bin/activate"
echo "2. Ejecutar servidor: python server.py"
echo "3. Ejecutar cliente: python client.py <IP_SERVIDOR> <ARCHIVO>"
