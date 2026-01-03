import sprites
from config import config

class Stager:
    def __init__(self, screen, reference_entity_dict):
        self.screen = screen
        self.entities = reference_entity_dict
        self.reset()

    def reset(self):
        self.grid = []
        self.entity_map = {}
        for k in self.entities:
            self.entities[k].clear()

    def load_stage(self, stage_path):
        self.reset()
        reading_map = reading_grid = False

        with open(stage_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue

                if line.startswith("entity_map"):
                    reading_map, reading_grid = True, False
                    continue
                if line.startswith("grid"):
                    reading_map, reading_grid = False, True
                    continue

                if reading_map:
                    if ":" not in line:
                        continue
                    idx_str, class_str = line.split(":", 1)
                    idx = int(idx_str.strip())
                    class_str = class_str.strip()
                    if class_str == "None":
                        self.entity_map[idx] = None
                    else:
                        # expect "sprites.ClassName"
                        try:
                            _, class_name = class_str.split(".", 1)
                            cls = getattr(sprites, class_name)
                        except Exception:
                            cls = None
                        self.entity_map[idx] = cls
                    continue

                if reading_grid:
                    row = [int(x.strip()) for x in line.split(",") if x.strip()]
                    if row:
                        self.grid.append(row)

        self._spawn()
        return self.entities

    def _spawn(self):
        for row_i, row in enumerate(self.grid):
            for col_i, cell in enumerate(row):
                cls = self.entity_map.get(cell)
                if not cls:
                    continue

                pos_x = col_i * (config.CELL_SIZE * config.resolution_scale)
                pos_y = row_i * (config.CELL_SIZE * config.resolution_scale)

                entity = cls()
                entity.summon(
                    target_row=row_i,
                    target_col=col_i,
                    target_pos_x=pos_x,
                    target_pos_y=pos_y,
                    screen=self.screen
                )

                if not hasattr(entity, "team"):
                    entity.team = "decor"
                    print("Error: No team has been assigned to", entity.__class__.__name__)

                print(entity.__class__.__name__)
                self.entities[entity.team].append(entity)
