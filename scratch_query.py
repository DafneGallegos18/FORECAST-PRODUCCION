import sys
import os
sys.path.append(os.path.abspath('c:/Users/Dafne Gallegos/.gemini/antigravity/scratch/production-forecast'))

from app.services.sap_connector import sap_connector

query = """
SELECT GroupCode, GroupName FROM OCRG WHERE GroupType = 'C'
"""
df = sap_connector.query(query)
print(df)
