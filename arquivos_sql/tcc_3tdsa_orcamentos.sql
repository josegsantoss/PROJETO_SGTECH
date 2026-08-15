-- MySQL dump 10.13  Distrib 8.0.46, for macos15 (arm64)
--
-- Host: 127.0.0.1    Database: tcc_3tdsa
-- ------------------------------------------------------
-- Server version	9.7.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;
SET @@SESSION.SQL_LOG_BIN= 0;

--
-- GTID state at the beginning of the backup 
--

SET @@GLOBAL.GTID_PURGED=/*!80000 '+'*/ '9e45e8cc-8c32-11f1-bd08-2e2d5524b624:1-967';

--
-- Table structure for table `orcamentos`
--

DROP TABLE IF EXISTS `orcamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orcamentos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `numero_orcamento` varchar(50) NOT NULL,
  `data_orcamento` date NOT NULL,
  `validade` date NOT NULL,
  `cliente_nome` varchar(150) NOT NULL,
  `cliente_doc` varchar(50) DEFAULT NULL,
  `cliente_contato` varchar(100) DEFAULT NULL,
  `vendedor` varchar(100) DEFAULT NULL,
  `subtotal` decimal(10,2) DEFAULT NULL,
  `desconto_percent` decimal(5,2) DEFAULT '0.00',
  `desconto_reais` decimal(10,2) DEFAULT '0.00',
  `frete` decimal(10,2) DEFAULT '0.00',
  `imposto_percent` decimal(5,2) DEFAULT '0.00',
  `total_geral` decimal(10,2) DEFAULT NULL,
  `metodo_pagamento` varchar(50) DEFAULT NULL,
  `condicao_pagamento` varchar(50) DEFAULT NULL,
  `garantia` varchar(50) DEFAULT NULL,
  `observacoes` text,
  `data_criacao` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `status` varchar(50) DEFAULT 'Pendente',
  `cliente_endereco` varchar(255) DEFAULT NULL,
  `cliente_cidade` varchar(100) DEFAULT NULL,
  `cliente_cep` varchar(20) DEFAULT NULL,
  `equipamento` varchar(100) DEFAULT NULL,
  `marca_modelo` varchar(100) DEFAULT NULL,
  `numero_serie` varchar(100) DEFAULT NULL,
  `problema_relatado` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `orcamentos`
--

LOCK TABLES `orcamentos` WRITE;
/*!40000 ALTER TABLE `orcamentos` DISABLE KEYS */;
/*!40000 ALTER TABLE `orcamentos` ENABLE KEYS */;
UNLOCK TABLES;
SET @@SESSION.SQL_LOG_BIN = @MYSQLDUMP_TEMP_LOG_BIN;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-14 22:35:32
