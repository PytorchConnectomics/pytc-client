# Train Model Runtime and TensorBoard

The standalone Monitor tab has been retired. Training status, runtime logs, and TensorBoard entry points now live on the Train Model page.

## How It Works

1. Navigate to **Train Model**.
2. Use the Train Model Runtime panel to check whether training is idle, running, complete, or failed.
3. Use **Show log** or **Details** to inspect failures.
4. After a successful run, use **TensorBoard** to open curves for the training output directory.
5. Use **Open Run Model** when the latest checkpoint is ready for inference.

## Requirements

- TensorBoard monitoring requires an active or completed training run with logs saved to the output directory.
- Runtime status should be interpreted from the Train Model panel, not from a separate Monitor tab.

## Tips

- If TensorBoard fails to open, make sure a training job has been started at least once and that the output path was set correctly in Train Model.
- TensorBoard updates in real time as new training data is written, so you can watch loss curves evolve during training.
- You can interact with TensorBoard normally in the opened TensorBoard page.
