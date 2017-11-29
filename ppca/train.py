import argparse
import sys

import numpy as np
import tensorflow as tf

from ppca import model, dataset
from common.experiment import Experiment


def print_graph(session, model, step, data):
    """
    A helper function for printing key training characteristics.
    """
    loss, mean, stddev = session.run([model.loss, model.data_dist_mean, model.data_dist_stddev])
    print("Model on step %d has loss = %f" % (step, loss))
    data["means"].append(mean.tolist())
    data["stddevs"].append(stddev.tolist())


def make_dataset(params):
    return dataset.normal_samples(params).make_one_shot_iterator()


def format_list(values):
    if type(values) is not list:
        return "%f" % values
    return "{%s}" % ",".join(map(format_list, values))


def format_data(data):
    template = """
means = %s;
stddevs = %s;
level = 0.035;

Table[
  ContourPlot[
    {
        PDF[MultinormalDistribution[{5, 10}, {{1.2^2, 0}, {0, 2.4^2} }], {x, y}] == level,
        PDF[MultinormalDistribution[means[[step]], stddevs[[step]]], {x, y}]  == level
    },
    {x, -1.5, 12.5},
    {y, -1.5, 12.5},
    PlotRange -> Full,
    MaxRecursion -> 10
  ],
  {step, 1, Length[means]}
]
"""
    return template % (format_list(data["means"]), format_list(data["stddevs"]))


def print_data(data):
    with open("train-data.txt", "w") as f:
        f.write(format_data(data))

def main(args):
    """
    The main function to train the model.
    """
    parser = argparse.ArgumentParser(description="Train the gan-normal model.")
    parser.add_argument("--experiment_dir", required=True, help="The expriment directory to store all the data")
    parser.add_argument("--load_checkpoint", help="Continue training from a checkpoint")
    parser.add_argument("--batch_size", type=int, default=32, help="The size of the minibatch")
    parser.add_argument("--learning_rate", type=float, default=0.01, help="The learning rate")
    parser.add_argument("--l2_reg", type=float, default=0.0005, help="The L2 regularization parameter")
    parser.add_argument("--latent_space_size", type=int, default=2, help="The latent space size")
    parser.add_argument("--input_mean", type=float, default=[], help="The mean of the input dataset", action="append")
    parser.add_argument("--input_stddev", type=float, default=[], help="The standard deviation of the input dataset", action="append")
    parser.add_argument("--max_steps", type=int, default=2000, help="The maximum number of steps to train training for")
    args = parser.parse_args(args)
    if len(args.input_mean) != len(args.input_stddev):
        print("There must be the same number of input means and standard deviations.")
        sys.exit(1)

    experiment = Experiment(args.experiment_dir)
    hparams = experiment.load_hparams(model.ModelParams, args)

    data = {
        "means": [],
        "stddevs": [],
    }

    # Create the model.
    dataset_value = make_dataset(dataset.DatasetParams(args))
    model_ops = model.PpcaModel(dataset_value, hparams, model.TrainingParams(args), args.batch_size)

    saver = tf.train.Saver()
    with tf.Session() as session:
        # Initializing the model. Either using a saved checkpoint or a ranrom initializer.
        if args.load_checkpoint:
            saver.restore(session, args.load_checkpoint)
        else:
            session.run(tf.global_variables_initializer())

        summary_writer = tf.summary.FileWriter(experiment.summaries_dir(), session.graph)

        # The main training loop. On each interation we train the model on one minibatch.
        global_step = session.run(model_ops.global_step)
        for _ in range(args.max_steps):
            print_graph(session, model_ops, global_step, data)
            session.run(model_ops.train)

            # Increment global step.
            session.run(model_ops.increment_global_step)
            global_step = session.run(model_ops.global_step)
            # And export all summaries to tensorboard.
            summary_writer.add_summary(session.run(model_ops.summaries), global_step)

        # Save experiment data.
        saver.save(session, experiment.checkpoint(global_step))

    print_data(data)


if __name__ == "__main__":
    main(sys.argv[1:])
