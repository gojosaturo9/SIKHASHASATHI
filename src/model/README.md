# Custom Liveness Model

This folder supports a project-trained anti-spoofing model. When
`src/model/liveness_model.joblib` exists, the attendance pipeline uses it before the
older ONNX model.

## Dataset Layout

Create this structure:

```text
src/model/liveness_dataset/
  live/
    student_001_real_1.jpg
    student_002_real_1.jpg
  spoof/
    print_attack/
      printed_photo_1.jpg
      paper_photo_1.jpg
    replay_attack/
      phone_screen_1.jpg
      laptop_screen_1.jpg
      replay_video_1.mp4
    3d_mask/
      mask_1.jpg
    partial_spoof/
      face_cutout_1.jpg
      eye_cut_mask_1.jpg
```

The app blocks all spoof classes as attacks. When enough subtype samples are
available, the saved model also reports the likely attack type:

```text
print_attack    printed photo, paper photo, printed cutout
replay_attack   phone/laptop/tablet screen, monitor display, replay video
3d_mask         3D face mask attacks
partial_spoof   cutouts, eye/mouth cut masks, partial face spoofing
```

Use at least two original files per subtype for the trainer to build an attack
type classifier. In practice, use many more: different people, lighting, camera
distances, paper quality, screens, and mask materials.

## IndicFairFace and ISGD/ISCG

IndicFairFace and the Indian Skincare and Grooming Dataset are useful for Indian
face diversity, but they are live/real-face datasets. They do not replace spoof
attack data. Use them to improve the live side of the classifier, then pair them
with printed-photo, phone-screen, laptop-screen, replay-video, and mask attack
samples.

Keep large external datasets outside the Git repo, for example:

```text
D:\datasets\IndicFairFace\
D:\datasets\ISGD\
D:\datasets\spoof_attacks\
```

Train with explicit labels:

```powershell
python -m src.model.train_liveness_model `
  --data src/model/liveness_dataset `
  --live-data D:\datasets\IndicFairFace `
  --live-data D:\datasets\ISGD `
  --print-attack-data D:\datasets\spoof_attacks\print_attack `
  --replay-attack-data D:\datasets\spoof_attacks\replay_attack `
  --mask-attack-data D:\datasets\spoof_attacks\3d_mask `
  --partial-spoof-data D:\datasets\spoof_attacks\partial_spoof `
  --max-per-class 2000 `
  --output src/model/liveness_model.joblib
```

Use `--max-per-class` when live datasets are much larger than the spoof set. A
balanced liveness model is usually better than a model trained on many thousands
of live faces and only a few spoof examples.

## CelebA-Spoof

CelebA-Spoof is a better fit for this feature than generic face datasets because
it includes live/spoof labels and spoof type annotations. Download it from the
official project/GitHub links and keep it outside this repo because it is large
and restricted to non-commercial research/education use.

The trainer can read CelebA-Spoof JSON label files directly:

```powershell
python -m src.model.train_liveness_model `
  --data src/model/liveness_dataset `
  --celeba-spoof-root D:\datasets\CelebA-Spoof `
  --celeba-spoof-labels D:\datasets\CelebA-Spoof\metas\intra_train\train_label.json `
  --celeba-spoof-labels D:\datasets\CelebA-Spoof\metas\intra_test\test_label.json `
  --max-per-class 8000 `
  --output src/model/liveness_model.joblib
```

CelebA-Spoof spoof type labels are mapped into this app's attack categories:

```text
Photo, Poster, A4, Face Mask, Upper Body Mask -> print_attack
PC, Pad, Phone                                  -> replay_attack
3D Mask                                        -> 3d_mask
Region Mask                                    -> partial_spoof
Live                                           -> live
```

If you only pass one spoof type, the app still trains live-vs-spoof detection.
To report attack subtypes, include at least two spoof categories with at least
two original files each.

Kaggle liveness video datasets are also supported. The trainer samples frames from
folders named `real`, `live`, `attack`, `spoof`, `print`, `monitor`, `phone`, `mask`,
and similar anti-spoofing labels.

## Kaggle Download

First configure Kaggle credentials by placing `kaggle.json` in:

```text
C:\Users\<you>\.kaggle\kaggle.json
```

Then install requirements and download a dataset:

```powershell
python -m pip install -r requirements.txt
python -m src.model.download_kaggle_dataset --dataset trainingdatapro/real-vs-fake-anti-spoofing-video-classification --output src/model/kaggle_liveness_data
```

If the full Kaggle archive is too large, download a balanced subset:

```powershell
python -m src.model.download_kaggle_subset --dataset trainingdatapro/real-vs-fake-anti-spoofing-video-classification --output src/model/kaggle_liveness_subset --per-class 12
```

Other useful Kaggle slugs to try:

```text
axondata/ibeta-level-1-paper-attacks
trainingdatapro/web-camera-face-liveness-detection
trainingdatapro/on-device-face-liveness-detection
```

Use images from the same type of classroom/camera setup that the app will see.
Collect multiple lighting conditions, distances, student skin tones, phone screens,
laptop screens, printed photos, and cropped paper photos. Do not train only on one
student or one background.

## Train

From the project root:

```powershell
python -m src.model.train_liveness_model --data src/model/liveness_dataset --output src/model/liveness_model.joblib
```

For the downloaded Kaggle dataset:

```powershell
python -m src.model.train_liveness_model --data src/model/kaggle_liveness_data --output src/model/liveness_model.joblib --frames-per-video 8
```

For the smaller subset:

```powershell
python -m src.model.train_liveness_model --data src/model/kaggle_liveness_subset --output src/model/liveness_model.joblib --frames-per-video 10
```

The script prints validation metrics and saves the model. Restart Streamlit after
training so the cached pipeline loads the new artifact.

## Tune Strictness

The app uses the model threshold saved in `liveness_model.joblib`. Higher values block
more spoof images but can also reject real faces in weak lighting.

```powershell
python -m src.model.train_liveness_model --threshold 0.72
```

For reliable classroom use, keep improving the dataset whenever a real face is blocked
or a spoof passes.
