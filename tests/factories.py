"""Deterministic valid documents and separate actor profiles."""

import factory
from django.contrib.auth import get_user_model

from nexora_backend.common.roles import Role
from nexora_backend.demands.models import Category, Demand
from nexora_backend.profiles.models import (
    ClientProfile,
    InvestorProfile,
    StartupProfile,
)
from nexora_backend.solutions.models import Solution


def cpf_for(number: int) -> str:
    result = f"{100000000 + number:09d}"
    for size in (9, 10):
        digit = (
            sum(int(char) * (size + 1 - index) for index, char in enumerate(result))
            * 10
            % 11
        )
        result += str(0 if digit == 10 else digit)
    return result


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"person{n}@example.test")
    nome_civil = "Private legal name"
    perfil_ativo = Role.CLIENT
    termo_privacidade_aceito = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "Strong-Password-42!")
        if create:
            self.save(update_fields=["password"])


class ClientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClientProfile

    user = factory.SubFactory(UserFactory)
    person_type = "PF"
    document = factory.Sequence(cpf_for)
    display_name = "Client"


class StartupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StartupProfile

    user = factory.SubFactory(UserFactory, perfil_ativo=Role.STARTUP)
    name = factory.Sequence(lambda n: f"Startup {n}")
    description = "Business solution"
    website = "https://example.test"


class InvestorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InvestorProfile

    user = factory.SubFactory(UserFactory, perfil_ativo=Role.INVESTOR)


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    slug = factory.Sequence(lambda n: f"category-{n}")
    name = "Operations"


class DemandFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Demand

    client = factory.SubFactory(ClientFactory)
    category = factory.SubFactory(CategoryFactory)
    title = "Improve operations"
    description = "A concrete business problem"


class SolutionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Solution

    demand = factory.SubFactory(DemandFactory)
    startup = factory.SubFactory(StartupFactory)
    proposal = "Private proposal"
