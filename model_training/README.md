# LOGICLENS Training - Google Colab Setup

This folder contains everything needed to train 4 fallacy detection models on Google Colab.

## 📁 Folder Structure

```
LOGICLENS_training/
├── data/                           # Training datasets
│   ├── edu_train.csv              # Education dataset (train)
│   ├── edu_dev.csv                # Education dataset (validation)
│   ├── edu_test.csv               # Education dataset (test)
│   ├── climate_train_mh.csv       # Climate dataset (train, multi-label)
│   ├── climate_dev_mh.csv         # Climate dataset (validation)
│   ├── climate_test_mh.csv        # Climate dataset (test)
│   └── mappings.csv               # Fallacy label mappings
├── scripts/                        # Training scripts
│   ├── logicedu.py                # Train EDU-based models
│   ├── logicclimate.py            # Train climate models
│   ├── library.py                 # Utility functions
│   └── weighted_cross_entropy.py  # Custom loss function
├── saved_models/                   # Pre-trained and output models
│   └── electra-base-mnli/         # Base model (110M params)
└── LOGICLENS_Training.ipynb          # Google Colab notebook (USE THIS!)
```

## 🚀 Quick Start Guide

### Step 1: Upload to Google Drive
1. Upload the entire `LOGICLENS_training` folder to your Google Drive root
2. Your path should be: `MyDrive/LOGICLENS_training/`

### Step 2: Open in Google Colab
1. Go to https://colab.research.google.com/
2. Click `File → Open notebook → Google Drive`
3. Navigate to `LOGICLENS_training/LOGICLENS_Training.ipynb`
4. Open it

### Step 3: Enable GPU
1. In Colab, click `Runtime → Change runtime type`
2. Select `T4 GPU` from Hardware accelerator
3. Click `Save`

### Step 4: Run Training
1. Run each cell sequentially (Shift + Enter)
2. When prompted, authorize Google Drive access
3. Wait for training to complete (~2-3 hours total)

## 📊 Training Details

| Model | Dataset | Epochs | GPU Time | Output Path |
|-------|---------|--------|----------|-------------|
| electra-logic | EDU | 10 | ~35 min | saved_models/electra-logic |
| electra-logic-structaware | EDU | 10 | ~35 min | saved_models/electra-logic-structaware |
| electra-logicclimate | Climate | 100* | ~20 min | saved_models/electra-logicclimate |
| electra-logicclimate-structaware | Climate | 100* | ~20 min | saved_models/electra-logicclimate-structaware |

*Early stopping typically stops at 20-40 epochs

## 💾 After Training

After training completes:
1. All trained models will be saved in `saved_models/` on your Google Drive
2. You can download them to your local machine
3. Copy them to your main project's `LOGICLENS/saved_models/` folder

## ⚙️ What Gets Trained

### Models 1 & 2: EDU Models
- **Base**: ELECTRA-base-mnli (pre-trained on MNLI task)
- **Fine-tuning**: Logical fallacy detection on education articles
- **Dataset**: ~2400 samples from LogicEdu/Quizizz
- **Fallacies**: 13 types (ad hominem, appeal to emotion, false causality, etc.)

### Models 3 & 4: Climate Models
- **Base**: Your trained electra-logic models
- **Fine-tuning**: Climate-specific fallacy detection
- **Dataset**: ~150 samples with multi-label annotations
- **Fallacies**: Climate change argument fallacies

### Structure-Aware vs Regular
- **Regular**: Uses raw text
- **Structure-Aware**: Uses argumentative discourse units (ADUs) marked with `[A]`, `[B]`, etc.

## 🔧 Troubleshooting

### "No GPU available"
- Make sure you selected GPU in Runtime → Change runtime type
- Free Colab GPU may have usage limits (12-24 hours per day)

### "Drive mount failed"
- Run the first cell again and authorize when prompted
- Check that LOGICLENS_training folder is in your Drive root

### "Module not found"
- The notebook installs all dependencies automatically
- If issues persist, restart runtime and run cells again

### Training seems slow
- Check GPU is enabled: Run `!nvidia-smi` in a cell
- T4 GPU should complete training in 2-3 hours total
- CPU fallback would take 30-40 hours

## 📝 Notes

- Training uses early stopping (patience=3), so it may stop before max epochs
- All models are automatically saved to your Google Drive
- You can safely close the browser tab during training (it will continue)
- To monitor progress, check the cell outputs or Drive folder

## 🎯 Expected Results

After successful training:
- 4 new model folders in `saved_models/`
- Each contains: `config.json`, `model.safetensors`, tokenizer files
- Total size: ~1.5 GB (4 models × ~400 MB each)

## ⏱️ Time Estimates

- **Google Colab (T4 GPU)**: 2-3 hours total
- **Local CPU**: 36+ hours total
- **Local GPU (RTX 3060/4060)**: 3-4 hours total

Good luck with training! 🚀
