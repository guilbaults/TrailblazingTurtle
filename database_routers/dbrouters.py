class DbRouter:
    """
    Implements a database router so that:

    * Django related data - DB alias `default`
    * slurm requests go to the MySQL database of slurm
    """
    def db_for_read(self, model, **hints):
        if 'ldap' in model._meta.db_table:
            return 'ldap'
        if model._meta.app_label == 'jobstats':
            return 'slurm'
        else:
            return None

    def db_for_write(self, model, **hints):
        if 'ldap' in model._meta.db_table:
            return False
        if model._meta.app_label == 'jobstats':
            return False
        else:
            return None

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._meta.app_label == 'jobstats' and obj2._meta.app_label == 'jobstats':
            return True
        elif 'jobstats' not in [obj1._meta.app_label, obj2._meta.app_label]:
            return True
        # by default return None - "undecided"

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # disallow any migration operation on ldap engine
        if 'ldap' in model._meta.db_table:
            return False
        # allow migrations on the "default" (django related data) DB
        if db == 'default' and app_label != 'jobstats':
            return True
        else:
            return False
