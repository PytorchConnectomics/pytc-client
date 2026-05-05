import numpy as np

from server_api.ehtool.router import _extract_marching_cubes_surface


class FakeMeasure:
    def __init__(self):
        self.steps = []

    def marching_cubes(self, _volume, level, step_size, allow_degenerate):
        self.steps.append(step_size)
        face_count = 120 if step_size == 1 else 40
        vertices = np.zeros((face_count * 3, 3), dtype=np.float32)
        faces = np.arange(face_count * 3, dtype=np.int64).reshape(face_count, 3)
        normals = np.zeros_like(vertices)
        values = np.zeros((vertices.shape[0],), dtype=np.float32)
        return vertices, faces, normals, values


def test_mesh_extraction_raises_stride_instead_of_dropping_faces():
    measure = FakeMeasure()

    _vertices, faces, _normals, _values, mesh_step = _extract_marching_cubes_surface(
        measure,
        np.zeros((4, 4, 4), dtype=np.float32),
        initial_step=1,
        face_limit=60,
    )

    assert measure.steps == [1, 2]
    assert mesh_step == 2
    assert faces.shape[0] == 40
