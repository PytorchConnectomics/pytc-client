# TensorBoard Monitoring Page

The Monitoring page displays a live TensorBoard dashboard embedded directly inside the application. TensorBoard is used to track and visualize training metrics such as loss curves, learning rate schedules, and validation scores.

## How It Works

1. Navigate to the **Tensorboard** tab in the top navigation bar.
2. If a training job is running (or has been run), TensorBoard will load automatically and display inside the page.
3. The dashboard shows the standard TensorBoard interface with all its features — scalar plots, image samples, histograms, etc.

## Requirements

- TensorBoard monitoring requires an active or completed training run with logs saved to the output directory.
- The server automatically starts a TensorBoard instance pointed at your training output directory when you launch training from the Train Model page.

## Tips

- If the TensorBoard panel appears blank, make sure a training job has been started at least once and that the output path was set correctly in the Train Model configuration.
- TensorBoard updates in real time as new training data is written, so you can watch loss curves evolve during training.
- You can interact with TensorBoard normally — zoom into charts, toggle runs on/off, and switch between the Scalars, Images, and other TensorBoard tabs within the embedded view.
