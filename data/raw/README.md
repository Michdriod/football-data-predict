# Data Directory

This directory contains raw CSV files from football-data.co.uk.

---

## 📥 How to Download Data

### 1. Visit football-data.co.uk

**URL**: https://www.football-data.co.uk/englandm.php

### 2. Download Premier League Data

Look for the **"Premier League"** section.

**League Code**: `E0`

Download CSV files for the seasons you need:

| Season | Filename | Status |
|--------|----------|--------|
| 2018/19 | E0_2018-19.csv | Recommended |
| 2019/20 | E0_2019-20.csv | Recommended |
| 2020/21 | E0_2020-21.csv | Recommended |
| 2021/22 | E0_2021-22.csv | Recommended |
| 2022/23 | E0_2022-23.csv | Recommended |
| 2023/24 | E0_2023-24.csv | Recommended |
| 2024/25 | E0_2024-25.csv | Current Season |

**Minimum**: 5 seasons (for sufficient training data)  
**Recommended**: 8-10 seasons (better model performance)

### 3. Save Files to This Directory

```bash
football-data-predict/
└── data/
    └── raw/
        ├── E0_2018-19.csv  ← Download here
        ├── E0_2019-20.csv
        ├── E0_2020-21.csv
        ├── E0_2022-23.csv
        ├── E0_2023-24.csv
        └── E0_2024-25.csv
```

**Important**: Keep the original filenames or use format: `E0_YYYY-YY.csv`

---

## 📋 CSV File Format

### Expected Columns

**Required** (minimum for basic functionality):
- `Div` - Division code (E0 for Premier League)
- `Date` - Match date (DD/MM/YYYY)
- `HomeTeam` - Home team name
- `AwayTeam` - Away team name
- `FTHG` - Full Time Home Goals
- `FTAG` - Full Time Away Goals
- `FTR` - Full Time Result (H/D/A)

**Recommended** (for full ML features):
- `HTHG`, `HTAG`, `HTR` - Half-time stats
- `HS`, `AS` - Shots (Home/Away)
- `HST`, `AST` - Shots on Target
- `HC`, `AC` - Corners
- `HY`, `AY` - Yellow Cards
- `HR`, `AR` - Red Cards
- `B365H`, `B365D`, `B365A` - Bet365 odds (Home/Draw/Away)
- `B365>2.5`, `B365<2.5` - Over/Under 2.5 goals odds

**Optional** (additional betting odds):
- Various bookmaker columns (BFDH, BMGMH, etc.)
- Closing odds (B365CH, B365CD, B365CA)
- Asian handicap columns

---

## 🚀 Loading Data

### Option 1: Load All Files in Directory

```bash
# From project root
cd /Users/mac/Desktop/football-data-predict

# Activate virtual environment
source pred/bin/activate

# Load all CSV files from data/raw/
python scripts/load_raw_data.py --data-dir data/raw/
```

This will:
- ✅ Validate all CSV files
- ✅ Check for duplicates
- ✅ Create backup of existing data
- ✅ Load to PostgreSQL
- ✅ Provide verification statistics

### Option 2: Load Single File

```bash
# Load just one season
python scripts/load_raw_data.py --file data/raw/E0_2024-25.csv
```

### Option 3: Force Reload (Replace All Data)

```bash
# WARNING: This replaces all existing data
python scripts/load_raw_data.py --data-dir data/raw/ --force-reload
```

---

## 🔄 Updating Data (Weekly/Monthly)

### During Active Season

1. **Download latest CSV** from football-data.co.uk
   - Updated weekly during season
   - Contains all matches played so far

2. **Save to data/raw/** (replace old file)
   ```bash
   # Example: Update current season
   # Download E0_2024-25.csv and save here
   ```

3. **Run update script**
   ```bash
   python scripts/update_data.py
   ```

This will:
- Load new data
- Run dbt transformations
- Validate data quality
- Update final ML dataset

### New Season

When a new season starts:

1. Download new season CSV (e.g., `E0_2025-26.csv`)
2. Save to `data/raw/`
3. Run update script
4. **Retrain models** with expanded dataset:
   ```bash
   python scripts/train_models.py
   ```

---

## 📊 Data Quality Checks

### After Loading

The loading script automatically checks:

- ✅ Required columns present
- ✅ No duplicate matches
- ✅ Valid date formats
- ✅ Team name consistency

### Additional Verification

```bash
# Check raw data in database
psql -d football_prediction_db -c "
SELECT 
    COUNT(*) as total_matches,
    MIN(\"Date\") as earliest,
    MAX(\"Date\") as latest
FROM raw_football_matches;
"

# Check final ML dataset
psql -d football_prediction_db -c "
SELECT COUNT(*) 
FROM public_public.fct_model_training_dataset;
"

# Run dbt tests
cd football_prediction
dbt test
```

---

## 🗂️ File Organization

### Good Practice

```
data/raw/
├── E0_2018-19.csv   # Oldest season
├── E0_2019-20.csv
├── E0_2020-21.csv
├── E0_2021-22.csv
├── E0_2022-23.csv
├── E0_2023-24.csv
└── E0_2024-25.csv   # Current season
```

### Avoid

```
❌ data/raw/premier_league.csv          # Generic name
❌ data/raw/matches.csv                 # No season info
❌ data/raw/2024.csv                    # Ambiguous format
❌ data/raw/E0_2024-25_backup.csv       # Keep backups elsewhere
```

---

## 🔒 Data Backup

Raw CSV files are **not backed up in git** (excluded by `.gitignore`).

**Recommendation**:
1. Keep original CSV files in cloud storage (Google Drive, Dropbox)
2. Database has automatic backups (created by load script)
3. Can always re-download from football-data.co.uk

---

## 📖 Column Reference

For detailed column descriptions, see:  
https://www.football-data.co.uk/notes.txt

**Key Columns**:
- **Match Info**: Div, Date, Time, HomeTeam, AwayTeam
- **Result**: FTHG, FTAG, FTR, HTHG, HTAG, HTR
- **Stats**: HS, AS, HST, AST, HC, AC, HF, AF, HY, AY, HR, AR
- **Odds**: B365*, BF*, BM*, BV*, BW*, CL*, LB*, PS*, Max*, Avg*
- **Over/Under**: *>2.5, *<2.5
- **Asian Handicap**: AHh, *AHH, *AHA

---

## ❓ Troubleshooting

### "No CSV files found"

```bash
# Check if files are in correct directory
ls -la data/raw/

# Should see .csv files, not subdirectories
```

### "Missing required columns"

CSV file might be from wrong source or corrupted.

✅ **Solution**: Re-download from football-data.co.uk

### "Duplicate matches found"

Same match appears multiple times (usually from multiple CSV files).

✅ **Solution**: Script will keep first occurrence automatically

### "File encoding error"

Some CSVs use different encoding.

✅ **Solution**: Open in Excel and re-save as UTF-8 CSV

---

## 📞 Support

If you encounter issues downloading or loading data:

1. Check football-data.co.uk is accessible
2. Verify CSV format matches expected structure
3. Review load script output for specific errors
4. Check database connection is working

---

*Last Updated: 2026-04-26*
