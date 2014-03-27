from ..core.parameterization.parameter_core import Observable
import itertools

class Cacher(object):
    """




    """

    def __init__(self, operation, limit=5, ignore_args=(), force_kwargs=()):
        self.limit = int(limit)
        self.ignore_args = ignore_args
        self.force_kwargs = force_kwargs
        self.operation=operation
        self.cached_inputs = []
        self.cached_outputs = []
        self.inputs_changed = []

    def __call__(self, *args, **kw):
        """
        A wrapper function for self.operation,
        """

        #ensure that specified arguments are ignored
        items = sorted(kw.items(), key=lambda x: x[0])
        oa_all = args + tuple(a for _,a in items)
        if len(self.ignore_args) != 0:
            oa = [a for i,a in itertools.chain(enumerate(args), items) if i not in self.ignore_args and i not in self.force_kwargs]
        else:
            oa = oa_all

        # this makes sure we only add an observer once, and that None can be in args
        observable_args = []
        for a in oa:
            if (not any(a is ai for ai in observable_args)) and a is not None:
                observable_args.append(a)

        #make sure that all the found argument really are observable:
        #otherswise don't cache anything, pass args straight though
        if not all([isinstance(arg, Observable) for arg in observable_args]):
            return self.operation(*args, **kw)

        if len(self.force_kwargs) != 0:
            # check if there are force args, which force reloading
            for k in self.force_kwargs:
                if k in kw and kw[k] is not None:
                    return self.operation(*args, **kw)
        # TODO: WARNING !!! Cache OFFSWITCH !!! WARNING
        # return self.operation(*args, **kw)

        #if the result is cached, return the cached computation
        state = [all(a is b for a, b in itertools.izip_longest(args, cached_i)) for cached_i in self.cached_inputs]
        try:
            if any(state):
                i = state.index(True)
                if self.inputs_changed[i]:
                    #(elements of) the args have changed since we last computed: update
                    self.cached_outputs[i] = self.operation(*args, **kw)
                    self.inputs_changed[i] = False
                return self.cached_outputs[i]
            else:
                #first time we've seen these arguments: compute

                #first make sure the depth limit isn't exceeded
                if len(self.cached_inputs) == self.limit:
                    args_ = self.cached_inputs.pop(0)
                    [a.remove_observer(self, self.on_cache_changed) for a in args_ if a is not None]
                    self.inputs_changed.pop(0)
                    self.cached_outputs.pop(0)
                #compute
                self.cached_inputs.append(oa_all)
                self.cached_outputs.append(self.operation(*args, **kw))
                self.inputs_changed.append(False)
                [a.add_observer(self, self.on_cache_changed) for a in observable_args]
                return self.cached_outputs[-1]#return
        except:
            self.reset()
            raise

    def on_cache_changed(self, direct, which=None):
        """
        A callback funtion, which sets local flags when the elements of some cached inputs change

        this function gets 'hooked up' to the inputs when we cache them, and upon their elements being changed we update here.
        """
        self.inputs_changed = [any([a is direct or a is which for a in args]) or old_ic for args, old_ic in zip(self.cached_inputs, self.inputs_changed)]

    def reset(self):
        """
        Totally reset the cache
        """
        [[a.remove_observer(self, self.on_cache_changed) for a in args if isinstance(a, Observable)] for args in self.cached_inputs]
        [[a.remove_observer(self, self.reset) for a in args if isinstance(a, Observable)] for args in self.cached_inputs]
        self.cached_inputs = []
        self.cached_outputs = []
        self.inputs_changed = []

    @property
    def __name__(self):
        return self.operation.__name__

from functools import partial, update_wrapper

class Cacher_wrap(object):
    def __init__(self, f, limit, ignore_args, force_kwargs):
        self.limit = limit
        self.ignore_args = ignore_args
        self.force_kwargs = force_kwargs
        self.f = f
        update_wrapper(self, self.f)
    def __get__(self, obj, objtype=None):
        return partial(self, obj)
    def __call__(self, *args, **kwargs):
        obj = args[0]
        #import ipdb;ipdb.set_trace()
        try:
            caches = obj.__cachers
        except AttributeError:
            caches = obj.__cachers = {}
        try:
            cacher = caches[self.f]
        except KeyError:
            cacher = caches[self.f] = Cacher(self.f, self.limit, self.ignore_args, self.force_kwargs)
        return cacher(*args, **kwargs)

class Cache_this(object):
    """
    A decorator which can be applied to bound methods in order to cache them
    """
    def __init__(self, limit=5, ignore_args=(), force_kwargs=()):
        self.limit = limit
        self.ignore_args = ignore_args
        self.force_args = force_kwargs
    def __call__(self, f):
        return Cacher_wrap(f, self.limit, self.ignore_args, self.force_args)