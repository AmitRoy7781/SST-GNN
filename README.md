# SST-GNN: Simplified Spatio-temporal Traffic forecasting model using Graph Neural Network
** Authors**
- [Amit Roy](https://github.com/AmitRoy7781)
- [Kashob Kumar Roy](https://github.com/forkkr)


This is a pytorch implementation of SST-GNN: Simplified Spatio-temporal Traffic forecasting model using Graph Neural Network
which has been accepted by PAKDD 2021.

# Requirements
Create a new conda Environment and install required packages(Commands are for ubuntu 16.04)

conda create -n TrafficEnv python=3.7
conda activate TrafficEnv
pip install -r requirements.txt


# Basic Usage:

Main Parameters:

- --dataset		The input traffic dataset(default:PeMSD7)
- --GNN_layers		Number of layers in GNN(default:3)
- --num_timestamps	Number of timestamps in Historical and current model(default:12)
- --pred_len		Traffic Prediction after how many timestamps(default:3)
- --epochs		Number of epochs during training(default:200)
- --seed			Random seed. (default: 824)
- --cuda			Use GPU if declared
- --save_model		Save model if declared
- --trained_model		Run pretrained model if declaired

# Example Usage

**Train Model Using:**

- python3 sst_gnn.py --cuda --dataset PeMSD7 --pred_len 3 --save_model


**Run Trained Model:**

- python3 sst_gnn.py --cuda --dataset PeMSD7  --pred_len 3 --trained_model
