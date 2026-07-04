from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)


class TransferProgress:
    """Rich-based progress display for Pyrogram/Kurigram upload/download callbacks.

    Usage::

        progress = TransferProgress("UP", "filename.mp4")
        await client.send_document(..., progress=progress.callback)
        progress.close()

    Each instance owns its own ``Progress`` context so that sequential
    file transfers never collide.
    """

    def __init__(self, label: str, name: str) -> None:
        self.label = label
        self.name = name

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[label]}[/] {task.fields[filename]}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            transient=False,
        )
        self._task_id = self._progress.add_task(
            self.name,
            total=0,
            label=self.label,
            filename=self.name,
        )
        self._progress.start()

    # -- Pyrogram/Kurigram progress callback ----------------------------------

    def callback(self, current: int, total: int) -> None:
        """Pyrogram-compatible progress callback ``(current, total)``."""
        if total > 0:
            self._progress.update(self._task_id, completed=current, total=total)

    def seed_total(self, total: int) -> None:
        """Set expected byte total before the first callback (e.g. from file size)."""
        if total > 0:
            self._progress.update(self._task_id, total=total)

    # -- Lifecycle ------------------------------------------------------------

    def close(self) -> None:
        """Stop the Rich progress display."""
        self._progress.stop()

    def newline(self) -> None:
        """Legacy helper — stops the progress display."""
        self.close()
