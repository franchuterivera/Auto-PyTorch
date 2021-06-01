import os
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import ConfigSpace.hyperparameters as CSH
from ConfigSpace.configuration_space import ConfigurationSpace

from autoPyTorch.pipeline.components.base_choice import autoPyTorchChoice
from autoPyTorch.pipeline.components.base_component import (
    ThirdPartyComponents,
    autoPyTorchComponent,
    find_components,
)
from autoPyTorch.pipeline.components.preprocessing.tabular_preprocessing.coalescer.base_coalescer import BaseCoalescer


coalescer_directory = os.path.split(__file__)[0]
_coalescer = find_components(__package__,
                             coalescer_directory,
                             BaseCoalescer)
_addons = ThirdPartyComponents(BaseCoalescer)


def add_coalescer(coalescer: BaseCoalescer) -> None:
    _addons.add_component(coalescer)


class CoalescerChoice(autoPyTorchChoice):
    """
    Allows for dynamically choosing coalescer component at runtime
    """

    def get_components(self) -> Dict[str, autoPyTorchComponent]:
        """Returns the available coalescer components

        Args:
            None

        Returns:
            Dict[str, autoPyTorchComponent]: all BaseCoalescer components available
                as choices for coalescer the categorical columns
        """
        components = OrderedDict()
        components.update(_coalescer)
        components.update(_addons.components)
        return components

    def get_hyperparameter_search_space(self,
                                        dataset_properties: Optional[Dict[str, Any]] = None,
                                        default: Optional[str] = None,
                                        include: Optional[List[str]] = None,
                                        exclude: Optional[List[str]] = None) -> ConfigurationSpace:
        cs = ConfigurationSpace()

        if dataset_properties is None:
            dataset_properties = dict()

        dataset_properties = {**self.dataset_properties, **dataset_properties}

        available_preprocessors = self.get_available_components(dataset_properties=dataset_properties,
                                                                include=include,
                                                                exclude=exclude)

        if len(available_preprocessors) == 0:
            raise ValueError("no coalescer found, please add a coalescer")

        if default is None:
            defaults = ['NoCoalescer', 'MinorityCoalescer']
            for default_ in defaults:
                if default_ in available_preprocessors:
                    if include is not None and default_ not in include:
                        continue
                    if exclude is not None and default_ in exclude:
                        continue
                    default = default_
                    break

        updates = self._get_search_space_updates()
        if '__choice__' in updates.keys():
            choice_hyperparameter = updates['__choice__']
            if not set(choice_hyperparameter.value_range).issubset(available_preprocessors):
                raise ValueError("Expected given update for {} to have "
                                 "choices in {} got {}".format(self.__class__.__name__,
                                                               available_preprocessors,
                                                               choice_hyperparameter.value_range))
            if len(dataset_properties['categorical_columns']) == 0:
                assert len(choice_hyperparameter.value_range) == 1
                assert 'MinorityCoalescer' in choice_hyperparameter.value_range, \
                    "Provided {} in choices, however, the dataset " \
                    "is incompatible with it".format(choice_hyperparameter.value_range)

            preprocessor = CSH.CategoricalHyperparameter('__choice__',
                                                         choice_hyperparameter.value_range,
                                                         default_value=choice_hyperparameter.default_value)
        else:
            # add only no coalescer to choice hyperparameters in case the dataset is only numerical
            if len(dataset_properties['categorical_columns']) == 0:
                default = 'NoCoalescer'
                if include is not None and default not in include:
                    raise ValueError("Provided {} in include, however, the dataset "
                                     "is incompatible with it".format(include))
                preprocessor = CSH.CategoricalHyperparameter('__choice__',
                                                             ['NoCoalescer'],
                                                             default_value=default)
            else:
                preprocessor = CSH.CategoricalHyperparameter('__choice__',
                                                             list(available_preprocessors.keys()),
                                                             default_value=default)

        cs.add_hyperparameter(preprocessor)

        # add only child hyperparameters of early_preprocessor choices
        for name in preprocessor.choices:
            updates = self._get_search_space_updates(prefix=name)
            # Call arg is ignored on mypy as the search space dynamically
            # provides different args
            preprocessor_configuration_space = available_preprocessors[name].\
                get_hyperparameter_search_space(dataset_properties,  # type:ignore[call-arg]
                                                **updates)
            parent_hyperparameter = {'parent': preprocessor, 'value': name}
            cs.add_configuration_space(name, preprocessor_configuration_space,
                                       parent_hyperparameter=parent_hyperparameter)

        self.configuration_space = cs
        self.dataset_properties = dataset_properties
        return cs

    def _check_dataset_properties(self, dataset_properties: Dict[str, Any]) -> None:
        """
        A mechanism in code to ensure the correctness of the fit dictionary
        It recursively makes sure that the children and parent level requirements
        are honored before fit.
        Args:
            dataset_properties:

        """
        super()._check_dataset_properties(dataset_properties)
        assert 'numerical_columns' in dataset_properties.keys(), \
            "Dataset properties must contain information about numerical columns"
        assert 'categorical_columns' in dataset_properties.keys(), \
            "Dataset properties must contain information about categorical columns"
