-- ============================================
-- RRO Database Schema - Complete Setup
-- ============================================
-- Run this script on a fresh database to create all tables with proper constraints
-- ============================================

-- Drop tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS ML_Analysis;
DROP TABLE IF EXISTS Bug_Comments;
DROP TABLE IF EXISTS Bug_stations;
DROP TABLE IF EXISTS Bug_Tests;
DROP TABLE IF EXISTS Bugs;
DROP TABLE IF EXISTS workgroup_assignments;
DROP TABLE IF EXISTS Workgroup_Schema;
DROP TABLE IF EXISTS Users;

-- ============================================
-- Users Table
-- ============================================
CREATE TABLE Users (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    First_Name VARCHAR(10) NOT NULL,
    Last_Name VARCHAR(10),
    Email VARCHAR(100) NOT NULL UNIQUE,
    Password VARCHAR(255) NOT NULL,
    Role ENUM('Engineer', 'Manager') NOT NULL,
    INDEX idx_role (Role),
    INDEX idx_email (Email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Workgroup_Schema Table
-- ============================================
CREATE TABLE Workgroup_Schema (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100),
    Release_Version VARCHAR(10) NOT NULL,
    Status ENUM('Completed', 'Active') NOT NULL DEFAULT 'Active',
    Manager_ID INT,
    Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Manager_ID) REFERENCES Users(ID) ON DELETE SET NULL,
    UNIQUE KEY uq_workgroup_name (Name),
    INDEX idx_manager (Manager_ID),
    INDEX idx_status (Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- workgroup_assignments Table
-- ============================================
CREATE TABLE workgroup_assignments (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Workgroup_ID INT NOT NULL,
    Employee_ID INT NOT NULL,
    FOREIGN KEY (Workgroup_ID) REFERENCES Workgroup_Schema(ID) ON DELETE CASCADE,
    FOREIGN KEY (Employee_ID) REFERENCES Users(ID) ON DELETE CASCADE,
    UNIQUE KEY unique_assignment (Workgroup_ID, Employee_ID),
    INDEX idx_workgroup (Workgroup_ID),
    INDEX idx_employee (Employee_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Bugs Table
-- ============================================
CREATE TABLE Bugs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    priority ENUM('P0', 'P1', 'P2', 'P3', 'P4') DEFAULT 'P2',
    bug_code VARCHAR(50) NOT NULL UNIQUE,
    bug_name VARCHAR(255),
    bug_type ENUM('repro', 'test') NOT NULL,
    engineer_id INT,
    workgroup_id INT NULL,
    summary VARCHAR(255),
    station_config VARCHAR(100),
    resource_group VARCHAR(100),
    status ENUM('pending', 'running', 'scheduled', 'completed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (engineer_id) REFERENCES Users(ID) ON DELETE SET NULL,
    FOREIGN KEY (workgroup_id) REFERENCES Workgroup_Schema(ID) ON DELETE SET NULL,
    INDEX idx_bug_code (bug_code),
    INDEX idx_engineer (engineer_id),
    INDEX idx_priority (priority),
    INDEX idx_status (status),
    INDEX idx_bug_type (bug_type),
    INDEX idx_bug_workgroup (workgroup_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Bug_Tests Table
-- ============================================
CREATE TABLE Bug_Tests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bug_id INT,
    test_name VARCHAR(100),
    configuration VARCHAR(50),
    FOREIGN KEY (bug_id) REFERENCES Bugs(id) ON DELETE CASCADE,
    INDEX idx_bug (bug_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Bug_stations Table
-- ============================================
CREATE TABLE Bug_stations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bug_id INT,
    station_name VARCHAR(100),
    FOREIGN KEY (bug_id) REFERENCES Bugs(id) ON DELETE CASCADE,
    INDEX idx_bug (bug_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Bug_Comments Table
-- ============================================
CREATE TABLE Bug_Comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bug_id INT,
    comment_bugzilla_id INT,
    creator VARCHAR(100),
    creation_time DATETIME,
    text TEXT,
    FOREIGN KEY (bug_id) REFERENCES Bugs(id) ON DELETE CASCADE,
    INDEX idx_bug (bug_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- ML_Analysis Table
-- ============================================
CREATE TABLE ML_Analysis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bug_id INT UNIQUE,
    repro_actions TEXT,
    config_changes TEXT,
    repro_readiness TEXT,
    summary TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bug_id) REFERENCES Bugs(id) ON DELETE CASCADE,
    INDEX idx_bug (bug_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Add Metadata Columns to Bug_Tests Table
-- ============================================
ALTER TABLE Bug_Tests
    ADD COLUMN test_plan_name VARCHAR(200) NULL,
    ADD COLUMN test_ring_name VARCHAR(100) NULL,
    ADD COLUMN execution_start DATETIME NULL,
    ADD COLUMN execution_end DATETIME NULL,
    ADD COLUMN controller_types VARCHAR(100) NULL,
    ADD COLUMN number_of_nodes INT NULL,
    ADD COLUMN failure_type VARCHAR(50) NULL,
    ADD COLUMN build_version VARCHAR(50) NULL,
    ADD COLUMN nfs_path VARCHAR(500) NULL,
    ADD COLUMN odin_link VARCHAR(500) NULL,
    ADD COLUMN signature VARCHAR(500) NULL,
    ADD COLUMN station_name VARCHAR(100) NULL;

-- ============================================
-- Verify Tables Created
-- ============================================
SHOW TABLES;

-- ============================================
-- Show Table Structures
-- ============================================
DESC Users;
DESC Workgroup_Schema;
DESC workgroup_assignments;
DESC Bugs;
DESC Bug_Tests;
DESC Bug_stations;
DESC Bug_Comments;
DESC ML_Analysis;
