import userportal.english_petname as english_petname
import hashlib


class petname:
    def __init__(self, seed):
        self.seed = seed
        self.len_names = len(english_petname.names)
        self.len_adverbs = len(english_petname.adverbs)
        self.len_adjectives = len(english_petname.adjectives)

    def anonymize(self, name):
        seeded_name = self.seed + name
        i = int(hashlib.sha1(seeded_name.encode()).hexdigest(), 16)

        pet_name = '{}-{}'.format(
            english_petname.adjectives[i % self.len_adjectives],
            english_petname.names[i % self.len_names])
        return pet_name


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Anonymise a username'
    )
    parser.add_argument('user', type=str, help='User name')
    args = parser.parse_args()

    # create the pet with the seed
    pet = petname('quuy3aew5moix5Ue1ahre9neimeeng')

    print(pet.anonymize(args.user))
