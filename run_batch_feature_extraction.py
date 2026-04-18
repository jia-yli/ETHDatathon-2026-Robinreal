import os
import pandas as pd
import sys

# Add directory to sys path so we can import preprocess_apartments
sys.path.append(os.path.abspath('robinreal_datathon_challenge_2026/raw_data'))
from preprocess_apartments import generate_apartment_attributes

raw_data_dir = 'robinreal_datathon_challenge_2026/raw_data'

files = [
    "robinreal_data_withimages-1776461278845.csv",
    "sred_data_withmontageimages_latlong.csv",
    "structured_data_withimages-1776412361239.csv",
    "structured_data_withoutimages-1776412361239.csv"
]

all_pkls = []

print("Starting batch feature extraction...")

for f in files:
    input_path = os.path.join(raw_data_dir, f)
    output_path = os.path.join(raw_data_dir, f"{f}_features.pkl")
    
    if os.path.exists(input_path):
        print(f"\nProcessing {f}...")
        generate_apartment_attributes(input_file=input_path, output_file=output_path, fill_na_false=False)
        all_pkls.append(output_path)
    else:
        print(f"⚠️ Warning: File {f} not found!")

# Concatenate all generated pickle files
print("\n" + "="*50)
print("Concatenating all extracted feature files...")
print("="*50)

df_list = []
for pkl in all_pkls:
    df = pd.read_pickle(pkl)
    print(f"Loaded {pkl} with {len(df)} rows.")
    df_list.append(df)

if df_list:
    final_df = pd.concat(df_list, ignore_index=True)
    # Deduplicate by 'id' just in case raw data overlaps
    initial_len = len(final_df)
    final_df = final_df.drop_duplicates(subset=['id'], keep='last').reset_index(drop=True)
    
    final_output = os.path.join(raw_data_dir, 'apartment_features_134.pkl')
    final_df.to_pickle(final_output)
    
    print(f"\n✅ Created unified {final_output}")
    print(f"Total rows matched: {len(final_df)} (dropped {initial_len - len(final_df)} duplicates)")
else:
    print("❌ No files were processed successfully.")
