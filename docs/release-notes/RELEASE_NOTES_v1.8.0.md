# QLC+ Swiss Knife v1.8.0 — meshes on the floor

### New
- **Stage & Meshes** (sidebar → Build the rig):
  - The 3D stage **seen from above and from the front**, with the fixtures and the meshes — band members, risers, drum kit, truss.
  - Place meshes by **what you see**: the centre on the stage and the height above the floor, instead of QLC+'s raw position numbers (which depend on how the model was drawn — that's why a bassist standing on the floor ends up at `Y −755` or `−900`).
  - The list shows which models **float** or **sink**, and by how much; **⤓ Put all on the floor** fixes them exactly.
  - Drag a mesh in either view; rotate and scale it while it stays on its spot and on the floor; duplicate, remove, relink its model file.
  - **Add models** from your mesh folders — they arrive in the centre of the stage, standing on the floor.
  - Change the stage type and size; the meshes keep their place.
- Wiki: how QLC+ 5 stores and places meshes, and where its floor is for each stage type.

Your original files are never changed: every result is a new `.qxw`, with a report next to it.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Stage and Meshes](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Stage-and-Meshes).
