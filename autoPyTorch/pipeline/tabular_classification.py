import copy
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

from ConfigSpace.configuration_space import Configuration, ConfigurationSpace
from ConfigSpace.forbidden import ForbiddenAndConjunction, ForbiddenEqualsClause

import numpy as np

import sklearn.preprocessing
from sklearn.base import ClassifierMixin

import torch

from autoPyTorch.constants import STRING_TO_TASK_TYPES
from autoPyTorch.datasets.base_dataset import BaseDatasetPropertiesType
from autoPyTorch.pipeline.base_pipeline import BasePipeline, PipelineStepType
from autoPyTorch.pipeline.components.base_choice import autoPyTorchChoice
from autoPyTorch.pipeline.components.base_component import autoPyTorchComponent
from autoPyTorch.pipeline.components.preprocessing.tabular_preprocessing.TabularColumnTransformer import (
    TabularColumnTransformer
)
from autoPyTorch.pipeline.components.preprocessing.tabular_preprocessing.encoding import (
    EncoderChoice
)
from autoPyTorch.pipeline.components.preprocessing.tabular_preprocessing.feature_preprocessing import (
    FeatureProprocessorChoice
)
from autoPyTorch.pipeline.components.preprocessing.tabular_preprocessing.imputation.SimpleImputer import SimpleImputer
from autoPyTorch.pipeline.components.preprocessing.tabular_preprocessing.scaling import ScalerChoice
from autoPyTorch.pipeline.components.setup.early_preprocessor.EarlyPreprocessing import EarlyPreprocessing
from autoPyTorch.pipeline.components.setup.lr_scheduler import SchedulerChoice
from autoPyTorch.pipeline.components.setup.network.base_network import NetworkComponent
from autoPyTorch.pipeline.components.setup.network_backbone import NetworkBackboneChoice
from autoPyTorch.pipeline.components.setup.network_embedding import NetworkEmbeddingChoice
from autoPyTorch.pipeline.components.setup.network_head import NetworkHeadChoice
from autoPyTorch.pipeline.components.setup.network_initializer import NetworkInitializerChoice
from autoPyTorch.pipeline.components.setup.optimizer import OptimizerChoice
from autoPyTorch.pipeline.components.training.data_loader.feature_data_loader import FeatureDataLoader
from autoPyTorch.pipeline.components.training.trainer import TrainerChoice
from autoPyTorch.utils.hyperparameter_search_space_update import HyperparameterSearchSpaceUpdates


class TabularClassificationPipeline(ClassifierMixin, BasePipeline):
    """This class is a proof of concept to integrate AutoSklearn Components

    It implements a pipeline, which includes as steps:

        ->One preprocessing step
        ->One neural network

    Contrary to the sklearn API it is not possible to enumerate the
    possible parameters in the __init__ function because we only know the
    available classifiers at runtime. For this reason the user must
    specifiy the parameters by passing an instance of
    ConfigSpace.configuration_space.Configuration.


    Args:
        config (Configuration)
            The configuration to evaluate.
        steps (Optional[List[Tuple[str, autoPyTorchChoice]]]): the list of steps that
            build the pipeline. If provided, they won't be dynamically produced.
        include (Optional[Dict[str, Any]]): Allows the caller to specify which configurations
            to honor during the creation of the configuration space.
        exclude (Optional[Dict[str, Any]]): Allows the caller to specify which configurations
            to avoid during the creation of the configuration space.
        random_state (np.random.RandomState): allows to produce reproducible results by
            setting a seed for randomized settings
        init_params (Optional[Dict[str, Any]])
        search_space_updates (Optional[HyperparameterSearchSpaceUpdates]):
            search space updates that can be used to modify the search
            space of particular components or choice modules of the pipeline

    Attributes:
    Examples
    """

    def __init__(
        self,
        config: Optional[Configuration] = None,
        steps: Optional[List[Tuple[str, autoPyTorchChoice]]] = None,
        dataset_properties: Optional[Dict[str, BaseDatasetPropertiesType]] = None,
        include: Optional[Dict[str, Any]] = None,
        exclude: Optional[Dict[str, Any]] = None,
        random_state: Optional[np.random.RandomState] = None,
        init_params: Optional[Dict[str, Any]] = None,
        search_space_updates: Optional[HyperparameterSearchSpaceUpdates] = None
    ):
        super().__init__(
            config, steps, dataset_properties, include, exclude,
            random_state, init_params, search_space_updates)

        # Because a pipeline is passed to a worker, we need to honor the random seed
        # in this context. A tabular classification pipeline will implement a torch
        # model, so we comply with https://pytorch.org/docs/stable/notes/randomness.html
        torch.manual_seed(self.random_state.get_state()[1][0])

    def _predict_proba(self, X: np.ndarray) -> np.ndarray:
        # Pre-process X
        loader = self.named_steps['data_loader'].get_loader(X=X)
        pred = self.named_steps['network'].predict(loader)
        if isinstance(self.dataset_properties['output_shape'], int):
            proba = pred[:, :self.dataset_properties['output_shape']]
            normalizer = proba.sum(axis=1)[:, np.newaxis]
            normalizer[normalizer == 0.0] = 1.0
            proba /= normalizer

            return proba

        else:
            raise ValueError("Expected output_shape to be integer, got {},"
                             "Tabular Classification only supports 'binary' and 'multiclass' outputs"
                             "got {}".format(type(self.dataset_properties['output_shape']),
                                             self.dataset_properties['output_type']))

    def predict_proba(self, X: np.ndarray, batch_size: Optional[int] = None) -> np.ndarray:
        """predict_proba.

        Args:
            X (np.ndarray): input to the pipeline, from which to guess targets
            batch_size (Optional[int]): batch_size controls whether the pipeline
                will be called on small chunks of the data. Useful when calling the
                predict method on the whole array X results in a MemoryError.
        Returns:
            np.ndarray: Probabilities of the target being certain class
        """
        if batch_size is None:
            y = self._predict_proba(X)

        else:
            if not isinstance(batch_size, int):
                raise ValueError("Argument 'batch_size' must be of type int, "
                                 "but is '%s'" % type(batch_size))
            if batch_size <= 0:
                raise ValueError("Argument 'batch_size' must be positive, "
                                 "but is %d" % batch_size)

            else:
                # Probe for the target array dimensions
                target = self.predict_proba(X[0:2].copy())

                y = np.zeros((X.shape[0], target.shape[1]),
                             dtype=np.float32)

                for k in range(max(1, int(np.ceil(float(X.shape[0]) / batch_size)))):
                    batch_from = k * batch_size
                    batch_to = min([(k + 1) * batch_size, X.shape[0]])
                    pred_prob = self.predict_proba(X[batch_from:batch_to], batch_size=None)
                    y[batch_from:batch_to] = pred_prob.astype(np.float32)

        # Neural networks might not be fit to produce a [0-1] output
        # For instance, after small number of epochs.
        y = np.clip(y, 0, 1)
        y = sklearn.preprocessing.normalize(y, axis=1, norm='l1')

        return y

    def score(self, X: np.ndarray, y: np.ndarray,
              batch_size: Optional[int] = None,
              metric_name: str = 'accuracy') -> float:
        """Scores the fitted estimator on (X, y)

        Args:
            X (np.ndarray):
                input to the pipeline, from which to guess targets
            batch_size (Optional[int]):
                batch_size controls whether the pipeline
                will be called on small chunks of the data.
                Useful when calling the predict method on
                the whole array X results in a MemoryError.
            y (np.ndarray):
                Ground Truth labels
            metric_name (str, default = 'accuracy'):
                 name of the metric to be calculated
        Returns:
            float: score based on the metric name
        """
        from autoPyTorch.pipeline.components.training.metrics.utils import get_metrics, calculate_score
        metrics = get_metrics(self.dataset_properties, [metric_name])
        y_pred = self.predict(X, batch_size=batch_size)
        score = calculate_score(y, y_pred, task_type=STRING_TO_TASK_TYPES[str(self.dataset_properties['task_type'])],
                                metrics=metrics)[metric_name]
        return score

    def _get_hyperparameter_search_space(self,
                                         dataset_properties: Dict[str, BaseDatasetPropertiesType],
                                         include: Optional[Dict[str, Any]] = None,
                                         exclude: Optional[Dict[str, Any]] = None,
                                         ) -> ConfigurationSpace:
        """Create the hyperparameter configuration space.

        For the given steps, and the Choices within that steps,
        this procedure returns a configuration space object to
        explore.

        Args:
            include (Optional[Dict[str, Any]]): what hyper-parameter configurations
                to honor when creating the configuration space
            exclude (Optional[Dict[str, Any]]): what hyper-parameter configurations
                to remove from the configuration space
            dataset_properties (Optional[Dict[str, BaseDatasetPropertiesType]]): Characteristics
                of the dataset to guide the pipeline choices of components

        Returns:
            cs (Configuration): The configuration space describing
                the SimpleRegressionClassifier.
        """
        cs = ConfigurationSpace()

        if not isinstance(dataset_properties, dict):
            warnings.warn('The given dataset_properties argument contains an illegal value.'
                          'Proceeding with the default value')
            dataset_properties = dict()

        if 'target_type' not in dataset_properties:
            dataset_properties['target_type'] = 'tabular_classification'
        if dataset_properties['target_type'] != 'tabular_classification':
            warnings.warn('Tabular classification is being used, however the target_type'
                          'is not given as "tabular_classification". Overriding it.')
            dataset_properties['target_type'] = 'tabular_classification'
        # get the base search space given this
        # dataset properties. Then overwrite with custom
        # classification requirements
        cs = self._get_base_search_space(
            cs=cs, dataset_properties=dataset_properties,
            exclude=exclude, include=include, pipeline=self.steps)

        # Here we add custom code, that is used to ensure valid configurations, For example
        # Learned Entity Embedding is only valid when encoder is one hot encoder
        if 'network_embedding' in self.named_steps.keys() and 'encoder' in self.named_steps.keys():
            embeddings = cs.get_hyperparameter('network_embedding:__choice__').choices
            if 'LearnedEntityEmbedding' in embeddings:
                encoders = cs.get_hyperparameter('encoder:__choice__').choices
                possible_default_embeddings = copy.copy(list(embeddings))
                del possible_default_embeddings[possible_default_embeddings.index('LearnedEntityEmbedding')]

                for encoder in encoders:
                    if encoder == 'OneHotEncoder':
                        continue
                    while True:
                        try:
                            cs.add_forbidden_clause(ForbiddenAndConjunction(
                                ForbiddenEqualsClause(cs.get_hyperparameter(
                                    'network_embedding:__choice__'), 'LearnedEntityEmbedding'),
                                ForbiddenEqualsClause(cs.get_hyperparameter('encoder:__choice__'), encoder)
                            ))
                            break
                        except ValueError:
                            # change the default and try again
                            try:
                                default = possible_default_embeddings.pop()
                            except IndexError:
                                raise ValueError("Cannot find a legal default configuration")
                            cs.get_hyperparameter('network_embedding:__choice__').default_value = default

        self.configuration_space = cs
        self.dataset_properties = dataset_properties
        return cs

    def _get_pipeline_steps(
        self,
        dataset_properties: Optional[Dict[str, BaseDatasetPropertiesType]],
    ) -> List[Tuple[str, PipelineStepType]]:
        """
        Defines what steps a pipeline should follow.
        The step itself has choices given via autoPyTorchChoice.

        Returns:
            List[Tuple[str, PipelineStepType]]:
                list of steps sequentially exercised by the pipeline.
        """
        steps = []  # type: List[Tuple[str, PipelineStepType]]
        default_dataset_properties: Dict[str, BaseDatasetPropertiesType] = {'target_type': 'tabular_classification'}
        if dataset_properties is not None:
            default_dataset_properties.update(dataset_properties)

        steps.extend([
            ("imputer", SimpleImputer(random_state=self.random_state)),
            ("encoder", EncoderChoice(default_dataset_properties, random_state=self.random_state)),
            ("scaler", ScalerChoice(default_dataset_properties, random_state=self.random_state)),
            ("feature_preprocessor", FeatureProprocessorChoice(default_dataset_properties,
                                                               random_state=self.random_state)),
            ("tabular_transformer", TabularColumnTransformer(random_state=self.random_state)),
            ("preprocessing", EarlyPreprocessing(random_state=self.random_state)),
            ("network_embedding", NetworkEmbeddingChoice(default_dataset_properties,
                                                         random_state=self.random_state)),
            ("network_backbone", NetworkBackboneChoice(default_dataset_properties,
                                                       random_state=self.random_state)),
            ("network_head", NetworkHeadChoice(default_dataset_properties,
                                               random_state=self.random_state)),
            ("network", NetworkComponent(random_state=self.random_state)),
            ("network_init", NetworkInitializerChoice(default_dataset_properties,
                                                      random_state=self.random_state)),
            ("optimizer", OptimizerChoice(default_dataset_properties,
                                          random_state=self.random_state)),
            ("lr_scheduler", SchedulerChoice(default_dataset_properties,
                                             random_state=self.random_state)),
            ("data_loader", FeatureDataLoader(random_state=self.random_state)),
            ("trainer", TrainerChoice(default_dataset_properties, random_state=self.random_state)),
        ])
        return steps

    def get_pipeline_representation(self) -> Dict[str, str]:
        """
        Returns a representation of the pipeline, so that it can be
        consumed and formatted by the API.

        It should be a representation that follows:
        [{'PreProcessing': <>, 'Estimator': <>}]

        Returns:
            Dict: contains the pipeline representation in a short format
        """
        preprocessing = []
        estimator = []
        skip_steps = ['data_loader', 'trainer', 'lr_scheduler', 'optimizer', 'network_init',
                      'preprocessing', 'tabular_transformer']
        for step_name, step_component in self.steps:
            if step_name in skip_steps:
                continue
            properties: Dict[str, Union[str, bool]] = {}
            if isinstance(step_component, autoPyTorchChoice) and step_component.choice is not None:
                properties = step_component.choice.get_properties()
            elif isinstance(step_component, autoPyTorchComponent):
                properties = step_component.get_properties()
            if 'shortname' in properties:
                if 'network' in step_name:
                    estimator.append(str(properties['shortname']))
                else:
                    preprocessing.append(str(properties['shortname']))
        return {
            'Preprocessing': ','.join(preprocessing),
            'Estimator': ','.join(estimator),
        }

    def _get_estimator_hyperparameter_name(self) -> str:
        """
        Returns the name of the current estimator.

        Returns:
            str: name of the pipeline type
        """
        return "tabular_classifier"
