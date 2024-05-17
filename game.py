import random

from constants import *

from manifold import Manifold
from water import Water
from objects import Object, Circle, Polygon, SquarePoly
from Vec2 import Vec2
from particle import Particle


def get_mp():
    """ Get mouse pos relative to the screen scale """
    return Vec2(*pg.mouse.get_pos()) / Values.RES_MUL


def holding_object(obj: Object, mp: Vec2):
    """ Reduce natural velocity and replace with a mouse force """
    # if isinstance(obj, Polygon):
    #     mp -= obj.size / 2  # middle of box

    max_f = Vec2(40, 40)
    force = Vec2(mp.x - obj.pos.x, mp.y - obj.pos.y) * Values.FPS / 60
    force.clamp_self(-max_f, max_f)
    force *= obj.mass

    obj.velocity *= Vec2(.85, .85)  # reduce natural velocity
    obj.apply_force(force * (obj.inv_mass * 100))


class Group:
    """ Group to store objects of different layers in order of lowest to highest. Optimised for retrieval of objects. """
    def __init__(self, add_objects=None):
        self.layer_nums = {}  # amount of stored objects with layer x
        self.objects = []  # ordered by layers, low - high

        if add_objects is not None:
            self.add_mul(add_objects)

    def add(self, obj):
        """ Add new layer to dict (if needed), insert object at end of objects' layer in list """
        if obj.layer not in self.layer_nums:
            self.layer_nums[obj.layer] = 0

        index = sum(amnt for layer, amnt in self.layer_nums.items() if layer <= obj.layer)  # index points to end of layer section in list

        self.objects.insert(index, obj)
        self.layer_nums[obj.layer] += 1

    def add_mul(self, lis: list):
        for obj in lis:
            self.add(obj)

    def remove_at_index(self, inx, obj=None):
        """ Fast method of removal. Returns successful deletion """
        if inx < len(self.objects):
            obj = obj if obj is not None else self.objects[inx]
            self.layer_nums[obj.layer] -= 1

            if self.layer_nums[obj.layer] <= 0:
                self.layer_nums.pop(obj.layer)

            del self.objects[inx]
            return True
        return False

    def remove_obj(self, o):
        """ Slow method of removal. Returns success on location, and deletion of object """
        try:
            found = [[i, obj] for i, obj in enumerate(self.objects) if obj == o][0]
            return self.remove_at_index(*found)
        except IndexError:
            return False

    def render_all(self, screen: pg.Surface):
        for obj in self.objects:
            obj.render(screen)

    def __repr__(self):
        return f'Group({len(self.objects)} objects, {len(self.layer_nums.keys())} layer/s)'


class Game:
    def __init__(self):
        self.running = True
        self.keys = pg.key.get_pressed()
        self.resolve_iterations = 8  # higher = more stable but less performant
        self.mp = get_mp()

        self.canvas_screen = pg.Surface(Vec2(Values.SCREEN_WIDTH, Values.SCREEN_HEIGHT).get())
        self.final_screen = pg.display.get_surface()

        # objects
        o1 = Circle(Vec2(10, 60), 7)
        o2 = Circle(Vec2(60, 60))
        o3 = Circle(Vec2(200, 30), 10)
        o4 = Circle(Vec2(120, 100), 20)
        pa = Polygon(Vec2(120, 40), [Vec2(0, 0), Vec2(15, 0), Vec2(15, 15), Vec2(0, 15)])
        self.pb = Polygon(Vec2(10, 10), [Vec2(0, 0), Vec2(15, 0), Vec2(15, 15)])

        g1 = SquarePoly(Vec2(50, 160), size=Vec2(200, 10), static=True)
        g2 = SquarePoly(Vec2(50, 75), size=Vec2(10, 100), static=True)
        g3 = SquarePoly(Vec2(250, 75), size=Vec2(10, 100), static=True)

        self.objects_group = Group([o1, o2, o3, o4, pa, self.pb, g1, g2, g3])
        self.particles_group = Group()
        self.collisions: list[Manifold] = []

        self.water = Water(100, 50, 250)

        # TESTING STUFF
        self.img = pg.Surface((40, 40), pg.SRCALPHA)
        c = Colours.DARKER_GREY
        pg.draw.circle(self.img, c, (20, 20), 15, 7)
        pg.draw.rect(self.img, c, pg.Rect((self.img.get_width() / 2) - 5, 0, 10, 10))
        pg.draw.rect(self.img, c, pg.Rect((self.img.get_width() / 2) - 5, 30, 10, 10))
        pg.draw.rect(self.img, c, pg.Rect(0, (self.img.get_height() / 2) - 5, 10, 10))
        pg.draw.rect(self.img, c, pg.Rect(30, (self.img.get_height() / 2) - 5, 10, 10))
        self.img_rot = 0

    def events(self):
        for event in pg.event.get():
            # key input
            if event.type == pg.KEYDOWN:
                self.keys = pg.key.get_pressed()

            if event.type == pg.KEYUP:
                self.keys = pg.key.get_pressed()

            # mouse
            if event.type == pg.MOUSEBUTTONDOWN and pg.mouse.get_pressed()[0]:
                r = 5
                p = self.mp.clone()
                p.y -= r + 10
                for _ in range(8):
                    self.particles_group.add(
                        Particle(p, velocity=Vec2(random.randrange(-50, 50), random.randrange(-100, -50)), colour=[random.randrange(0, 255) for _ in range(3)], lifetime=random.random() + 0.4)
                    )

                for i in range(1):
                    b = Circle(p, r)
                    b.colour = [random.randrange(0, 255) for _ in range(3)]
                    self.objects_group.add(b)

            if event.type == pg.MOUSEBUTTONUP and not pg.mouse.get_pressed()[0]:
                pass

            # close game
            if event.type == pg.QUIT or self.keys[pg.K_ESCAPE]:
                self.running = False

    def rotate_screen_blit(self, image, angle, pos: Vec2):
        """ Temporary """
        rotated_image = pg.transform.rotate(image, angle)
        new_rect = rotated_image.get_rect(center=image.get_rect(topleft=pos.get()).center)
        pg.draw.rect(self.canvas_screen, Colours.DARK_GREY, new_rect, 1)

        self.canvas_screen.blit(rotated_image, new_rect)

    def init_collisions(self, objs: list):
        """ Iterate over all objects given and check if they're colliding. If so, fill manifold values & add it to collision list """
        for ia, a in enumerate(objs):
            for b in objs[ia + 1:]:  # prevent duplicate checks (and self checks)
                if a.should_ignore_collision(b):
                    continue

                ch = Manifold(a, b)
                ch.init_collision()

                if ch.contact_count > 0:
                    self.collisions.append(ch)

    def update_objects(self):
        objects = self.objects_group.objects

        self.collisions.clear()
        self.init_collisions(objects)

        # apply left-over velocity
        for obj in objects:
            obj.update_velocity(Values.DT)

        # resolve collisions, apply impulses
        for it in range(self.resolve_iterations):
            for coll in self.collisions:
                coll.resolve_collision()

        # apply velocity
        for obj in objects:
            obj.update(Values.DT)

        # correct positions
        for coll in self.collisions:
            coll.positional_correction()

        # conclusion
        for i, obj in enumerate(objects):
            obj.force.set(0, 0)

            if obj.is_out_of_bounds():
                self.objects_group.remove_at_index(i, obj)

    def update_particles(self):
        for i, part in enumerate(self.particles_group.objects):
            if part.should_del():
                self.particles_group.remove_at_index(i, part)
            part.update(Values.DT)

    def update(self):
        holding_object(self.pb, self.mp)

        self.water.update()

        self.update_particles()
        self.update_objects()

    def render(self):
        self.final_screen.fill(Colours.BG_COL)
        self.canvas_screen.fill(Colours.BG_COL)

        # render here
        self.water.render(self.canvas_screen)

        self.particles_group.render_all(self.canvas_screen)
        self.objects_group.render_all(self.canvas_screen)

        for coll in self.collisions:
            coll.render(self.canvas_screen)

        # outline
        pg.draw.rect(self.canvas_screen, Colours.BG_COL, pg.Rect((0, 0), (Values.SCREEN_WIDTH, Values.SCREEN_HEIGHT)), 5)
        pg.draw.rect(self.canvas_screen, Colours.WHITE, pg.Rect(1, 1, Values.SCREEN_WIDTH - 2, Values.SCREEN_HEIGHT - 2), 1)
        pg.draw.rect(self.canvas_screen, Colours.WHITE, pg.Rect(4, 4, Values.SCREEN_WIDTH - 8, Values.SCREEN_HEIGHT - 8), 2)

        # test renders
        self.rotate_screen_blit(self.img, self.img_rot, Vec2(50, 40))
        self.img_rot += 60 * Values.DT

        # final
        scaled = pg.transform.scale(self.canvas_screen, Vec2(Values.SCREEN_WIDTH * Values.RES_MUL, Values.SCREEN_HEIGHT * Values.RES_MUL).get())
        self.final_screen.blit(scaled, (0, 0))
        pg.display.flip()

    def main_loop(self):
        """ Called every on frame """
        self.mp = get_mp()

        self.events()
        self.update()
        self.render()
