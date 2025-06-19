#!/usr/bin/env python3
import grpc
from concurrent import futures
import os
import hashlib
import time
from pathlib import Path
import logging

# Importa los archivos generados por protoc
import file_transfer_pb2
import file_transfer_pb2_grpc

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FileTransferServicer(file_transfer_pb2_grpc.FileTransferServiceServicer):
    def __init__(self, upload_dir="./uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)
        
    def TransferFile(self, request_iterator, context):
        """Recibe archivo en chunks via streaming"""
        filename = None
        file_path = None
        total_bytes = 0
        chunks_received = 0
        start_time = time.time()
        
        try:
            with open(file_path, 'wb') if file_path else None as f:
                for chunk in request_iterator:
                    if filename is None:
                        filename = chunk.filename
                        file_path = self.upload_dir / filename
                        logger.info(f"Iniciando recepción de archivo: {filename}")
                        f = open(file_path, 'wb')
                    
                    f.write(chunk.data)
                    total_bytes += len(chunk.data)
                    chunks_received += 1
                    
                    if chunks_received % 100 == 0:  # Log cada 100 chunks
                        logger.info(f"Recibidos {chunks_received} chunks, {total_bytes / (1024*1024):.2f} MB")
                    
                    if chunk.is_last_chunk:
                        break
                        
                if f:
                    f.close()
            
            end_time = time.time()
            transfer_time = end_time - start_time
            speed_mbps = (total_bytes / (1024*1024)) / transfer_time
            
            logger.info(f"Archivo {filename} recibido completamente:")
            logger.info(f"  - Tamaño: {total_bytes / (1024*1024*1024):.2f} GB")
            logger.info(f"  - Tiempo: {transfer_time:.2f} segundos")
            logger.info(f"  - Velocidad: {speed_mbps:.2f} MB/s")
            
            return file_transfer_pb2.TransferResponse(
                success=True,
                message=f"Archivo {filename} recibido exitosamente",
                bytes_received=total_bytes
            )
            
        except Exception as e:
            logger.error(f"Error durante la transferencia: {str(e)}")
            return file_transfer_pb2.TransferResponse(
                success=False,
                message=f"Error: {str(e)}",
                bytes_received=total_bytes
            )
    
    def GetFileInfo(self, request, context):
        """Obtiene información de un archivo"""
        file_path = self.upload_dir / request.filename
        
        if file_path.exists():
            file_size = file_path.stat().st_size
            
            # Calcula checksum MD5
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            
            return file_transfer_pb2.FileInfoResponse(
                exists=True,
                file_size=file_size,
                checksum=hash_md5.hexdigest()
            )
        else:
            return file_transfer_pb2.FileInfoResponse(
                exists=False,
                file_size=0,
                checksum=""
            )

def serve(port=50051, max_workers=50):
    """Inicia el servidor gRPC"""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ('grpc.keepalive_time_ms', 60000),
            ('grpc.keepalive_timeout_ms', 10000),
            ('grpc.keepalive_permit_without_calls', True),
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.http2.min_time_between_pings_ms', 10000),
            ('grpc.http2.min_ping_interval_without_data_ms', 300000),
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
            ('grpc.max_send_message_length', 100 * 1024 * 1024),     # 100MB
        ]
    )
    
    file_transfer_pb2_grpc.add_FileTransferServiceServicer_to_server(
        FileTransferServicer(), server
    )
    
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)
    
    logger.info(f"Servidor iniciado en puerto {port}")
    logger.info(f"Máximo {max_workers} workers concurrentes")
    
    server.start()
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Deteniendo servidor...")
        server.stop(0)

if __name__ == '__main__':
    serve()