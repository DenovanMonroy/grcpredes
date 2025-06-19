#!/usr/bin/env python3
import grpc
import os
import time
import hashlib
from pathlib import Path
import logging

# Importa los archivos generados por protoc
import file_transfer_pb2
import file_transfer_pb2_grpc

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FileTransferClient:
    def __init__(self, server_ip, server_port=50051):
        self.server_ip = server_ip
        self.server_port = server_port
        self.chunk_size = 1024 * 1024  # 1MB chunks para optimizar velocidad
        
    def _get_channel(self):
        """Crea un canal gRPC optimizado"""
        options = [
            ('grpc.keepalive_time_ms', 60000),
            ('grpc.keepalive_timeout_ms', 10000),
            ('grpc.keepalive_permit_without_calls', True),
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.http2.min_time_between_pings_ms', 10000),
            ('grpc.http2.min_ping_interval_without_data_ms', 300000),
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
            ('grpc.max_send_message_length', 100 * 1024 * 1024),     # 100MB
        ]
        
        return grpc.insecure_channel(f'{self.server_ip}:{self.server_port}', options=options)
    
    def _generate_file_chunks(self, file_path):
        """Genera chunks del archivo para streaming"""
        file_path = Path(file_path)
        filename = file_path.name
        file_size = file_path.stat().st_size
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        
        logger.info(f"Enviando archivo: {filename}")
        logger.info(f"Tamaño: {file_size / (1024*1024*1024):.2f} GB")
        logger.info(f"Total chunks: {total_chunks}")
        
        chunk_number = 0
        bytes_sent = 0
        
        with open(file_path, 'rb') as f:
            while True:
                chunk_data = f.read(self.chunk_size)
                if not chunk_data:
                    break
                    
                chunk_number += 1
                bytes_sent += len(chunk_data)
                is_last = chunk_number == total_chunks
                
                yield file_transfer_pb2.FileChunk(
                    filename=filename,
                    data=chunk_data,
                    chunk_number=chunk_number,
                    total_chunks=total_chunks,
                    is_last_chunk=is_last
                )
                
                # Log progreso cada 100 chunks
                if chunk_number % 100 == 0:
                    progress = (bytes_sent / file_size) * 100
                    logger.info(f"Progreso: {progress:.1f}% ({bytes_sent / (1024*1024):.2f} MB enviados)")
                
                if is_last:
                    break
    
    def send_file(self, file_path):
        """Envía un archivo al servidor"""
        start_time = time.time()
        
        try:
            with self._get_channel() as channel:
                stub = file_transfer_pb2_grpc.FileTransferServiceStub(channel)
                
                logger.info(f"Conectando a servidor {self.server_ip}:{self.server_port}")
                
                # Enviar archivo via streaming
                response = stub.TransferFile(self._generate_file_chunks(file_path))
                
                end_time = time.time()
                transfer_time = end_time - start_time
                
                if response.success:
                    speed_mbps = (response.bytes_received / (1024*1024)) / transfer_time
                    logger.info(f"✅ Transferencia exitosa:")
                    logger.info(f"   - Bytes enviados: {response.bytes_received / (1024*1024*1024):.2f} GB")
                    logger.info(f"   - Tiempo total: {transfer_time:.2f} segundos")
                    logger.info(f"   - Velocidad promedio: {speed_mbps:.2f} MB/s")
                    return True
                else:
                    logger.error(f"❌ Error en transferencia: {response.message}")
                    return False
                    
        except grpc.RpcError as e:
            logger.error(f"❌ Error gRPC: {e.code()} - {e.details()}")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado: {str(e)}")
            return False
    
    def verify_file(self, filename, local_path):
        """Verifica si el archivo fue transferido correctamente"""
        try:
            with self._get_channel() as channel:
                stub = file_transfer_pb2_grpc.FileTransferServiceStub(channel)
                
                request = file_transfer_pb2.FileInfoRequest(filename=filename)
                response = stub.GetFileInfo(request)
                
                if response.exists:
                    # Calcula checksum del archivo local
                    local_checksum = self._calculate_md5(local_path)
                    
                    if local_checksum == response.checksum:
                        logger.info("✅ Verificación exitosa: Los archivos coinciden")
                        return True
                    else:
                        logger.error("❌ Verificación fallida: Los checksums no coinciden")
                        return False
                else:
                    logger.error("❌ El archivo no existe en el servidor")
                    return False
                    
        except Exception as e:
            logger.error(f"Error durante verificación: {str(e)}")
            return False
    
    def _calculate_md5(self, file_path):
        """Calcula MD5 hash de un archivo"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

def main():
    import sys
    
    if len(sys.argv) != 3:
        print("Uso: python client.py <IP_SERVIDOR> <RUTA_ARCHIVO>")
        print("Ejemplo: python client.py 192.168.1.100 /ruta/a/archivo_grande.zip")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    file_path = sys.argv[2]
    
    if not os.path.exists(file_path):
        logger.error(f"El archivo {file_path} no existe")
        sys.exit(1)
    
    client = FileTransferClient(server_ip)
    
    logger.info("=== Iniciando transferencia de archivo ===")
    success = client.send_file(file_path)
    
    if success:
        logger.info("=== Verificando integridad del archivo ===")
        filename = Path(file_path).name
        client.verify_file(filename, file_path)
    
    logger.info("=== Proceso completado ===")

if __name__ == '__main__':
    main()