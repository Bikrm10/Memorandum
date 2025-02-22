USE memo;
CREATE TABLE memo_store(
    id INT AUTO_INCREMENT PRIMARY KEY,             
    subject VARCHAR(255) NOT NULL,                 
    background TEXT,                               
    proposal TEXT,                                 
    recommendation TEXT,                           
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP 
);
