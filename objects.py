import math

from constants import *
from Vec2 import Vec2


DEF_STATIC = False
DEF_MAT = Materials.TESTING
DEF_LAYER = 10


class Material:
    def __init__(self, mat: Materials):
        self.restitution: float = mat[Materials.REST]
        self.density: float = mat[Materials.DENS]

    def __repr__(self):
        return f'Material(rest: {self.restitution}, dens: {self.density})'


class Object:
    def __init__(self, pos: Vec2, static=DEF_STATIC, material=DEF_MAT, layer=DEF_LAYER):
        self._type = 'Object'
        self._og_pos = pos.clone()
        self.pos = pos
        self.static = static
        self.layer = layer

        # texture
        self.colour = Colours.WHITE
        self._outline_size = 2

        # linear properties
        self.velocity: Vec2 = Vec2()
        self.force: Vec2 = Vec2()
        self.static_friction: float = 0.5  # at rest
        self.dynamic_friction: float = 0.3  # already moving

        # angular properties
        self.orientation: float = 0  # in radians
        self.angular_velocity: Vec2 = Vec2()
        self.torque: float = 0

        # mass
        self.material = Material(material)
        self.mass = 0
        self.inv_mass = 0
        self.inertia = 0
        self.inv_inertia = 0

    def apply_force(self, force: Vec2):
        """ Apply external force to object """
        self.force += force

    def apply_impulse(self, impulse: Vec2, contact_vec: Vec2):
        """ Apply given impulse to self (multiplied by inv_mass) """
        if not self.static:
            self.velocity.add_self(impulse, self.inv_mass)

    def is_out_of_bounds(self, check_top=False):
        """ Is object too far from screen bounds to be considered worth keeping alive """
        above = self.pos.y < 0 - Values.SCREEN_HEIGHT
        below = self.pos.y > Values.SCREEN_HEIGHT * 2
        left = self.pos.x < 0 - Values.SCREEN_WIDTH
        right = self.pos.x > Values.SCREEN_WIDTH * 2
        return below or left or right or (check_top and above)

    def static_correction(self):
        """ Reset velocity on static objects """
        if self.static:
            self.velocity.set(0, 0)

    def should_ignore_collision(self, b):
        """ Checks whether both are static OR on different layers and neither are static """
        both_static = self.static and b.static
        one_static = self.static or b.static
        not_on_layer = self.layer != b.layer
        return both_static or (not_on_layer and not one_static)

    def update_velocity(self, dt):
        """ Should be called twice - before updating pos and after - for each physics calculation """
        if not self.static:
            dt_h = dt * 0.5
            self.velocity.add_self(self.force, dt_h)  # external force

            self.velocity.add_self(Forces.GRAVITY, dt_h)
            self.velocity.add_self(Forces.AIR_VELOCITY, dt_h)

    def update(self, dt):
        """ See README on better dt """
        self.pos += self.velocity * dt

        self.update_velocity(dt)
        self.static_correction()

    def __repr__(self):
        return f'{self._type}(layer: {self.layer})'


class Circle(Object):
    def __init__(self, pos: Vec2, radius=5, static=DEF_STATIC, material=DEF_MAT, layer=DEF_LAYER):
        super().__init__(pos, static, material, layer)
        self._type = 'Ball'
        self.radius = radius

        # lowered friction
        self.static_friction = 0.1
        self.dynamic_friction = 0.05

        self.compute_mass()

    def compute_mass(self):
        mass = math.pi * self.radius * self.radius * self.material.density
        self.mass = Forces.INF_MASS if self.static else mass
        self.inv_mass = 0 if self.static else 1 / self.mass

        self.inertia = self.mass * self.radius * self.radius
        self.inv_inertia = 0 if self.static else 1 / self.inertia

    def render(self, screen: pg.Surface):
        ps = 1  # half of line size
        pg.draw.line(screen, self.colour,
                     Vec2(self.pos.x - ps, self.pos.y).get(), Vec2(self.pos.x - ps, self.pos.y - self.radius).get(), 2)
        pg.draw.circle(screen, self.colour, self.pos.get(), ps)
        pg.draw.circle(screen, self.colour, self.pos.get(), self.radius, 2)


class Square(Object):
    def __init__(self, pos: Vec2, size: Vec2 = Vec2(10, 10), static=DEF_STATIC, material=DEF_MAT, layer=DEF_LAYER):
        super().__init__(pos, static, material, layer)
        self._type = 'Box'
        self.size = size

        self.compute_mass()

    @property
    def lower_pos(self):
        return self.pos + self.size

    def compute_mass(self):
        mass = self.material.density * self.size.x * self.size.y
        self.mass = Forces.INF_MASS if self.static else mass
        self.inv_mass = 0 if self.static else 1 / self.mass

    def render(self, screen: pg.Surface):
        pg.draw.line(screen, self.colour, self.pos.get(), (self.lower_pos - 1).get())
        pg.draw.rect(screen, self.colour, pg.Rect(self.pos.get(), self.size.get()), self._outline_size)


class Polygon(Object):
    MIN_VERTEX_COUNT = 3
    MAX_VERTEX_COUNT = 16

    def __init__(self, pos: Vec2, vertices=None, static=DEF_STATIC, material=DEF_MAT, layer=DEF_LAYER):
        super().__init__(pos, static, material, layer)
        self._type = 'Poly'
        self.vertex_count = 0
        self.vertices: list[Vec2] = []
        self.normals: list[Vec2] = []

        if vertices is not None:
            self.set(vertices)

    def compute_mass(self):
        """ Add all triangle areas of polygon for mass. Sets position to the centre of mass. """
        com = Vec2()  # centre of mass
        area = 0.0
        inertia = 0.0

        K_INV3: float = 1 / 3

        for i in range(self.vertex_count):
            p1: Vec2 = self.vertices[i]
            p2: Vec2 = self.vertices[(i + 1) % self.vertex_count]  # loop back to 0 if exceeding v count

            derivative: float = p1.cross_vec(p2)
            tri_area = 0.5 * derivative

            area += tri_area

            # Use area to weight the centroid average, not just vertex position
            weight: float = tri_area * K_INV3
            com.add_self(p1, weight)
            com.add_self(p2, weight)

            intx2: float = (p1.x ** 2) + (p2.x * p1.x) + (p2.x ** 2)
            inty2: float = (p1.y ** 2) + (p2.y * p1.y) + (p2.y ** 2)
            inertia += (.25 * K_INV3 * derivative) * (intx2 + inty2)

        com *= 1 / area
        self.pos = self._og_pos + com

        # translate vertices to centroid (centroid 0, 0)
        for i in range(self.vertex_count):
            self.vertices[i] -= com

        self.mass = self.material.density * area
        self.inv_mass = 0 if self.static else 1 / self.mass
        self.inertia = inertia * self.material.density
        self.inv_inertia = 0 if self.static else 1 / self.inertia

    def set(self, verts: list[Vec2]):
        # todo: do more stuff here
        self.vertices = verts
        self.vertex_count = len(verts)

        # compute normals for each face
        for i in range(self.vertex_count):
            face: Vec2 = self.vertices[(i + 1) % self.vertex_count] - self.vertices[i]

            normal = Vec2(face.y, -face.x)   # calculate normal with 2D cross product between vector and scalar
            self.normals.append(normal.normalise_self())

        self.compute_mass()

    def render(self, screen: pg.Surface):
        pg.draw.rect(screen, Colours.RED, pg.Rect(self.pos.get(), (1, 1)))
