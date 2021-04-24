# SST-GNN: Simplified Spatio-temporal Traffic forecasting model using Graph Neural Network

**Authors**
- [Amit Roy](https://amitroy7781.github.io/)
- [Kashob Kumar Roy](https://www.linkedin.com/in/forkkr/) 
- [Amin Ahsan Ali](http://www.cse.iub.edu.bd/faculties/53)
- [M Ashraful Amin](http://www.cse.iub.edu.bd/faculties/25) 
- [A K M Mahbubur Rahman](http://www.cse.iub.edu.bd/faculties/56)

This is the official pytorch implementation of our [paper](https://arxiv.org/abs/2104.00055) SST-GNN: Simplified Spatio-temporal Traffic forecasting model using Graph Neural Network which has been accepted by PAKDD 2021. Check the video presentation of our paper [here](https://youtu.be/Vl4P5IfbuE4).

# Abstract

To capture spatial relationships and temporal dynamics in traffic data, spatio-temporal models for traffic forecasting have drawn significant attention in recent years. Most of the recent works employed graph neural networks(GNN) with multiple layers to capture the spatial dependency. However, road junctions with different hop-distance can carry distinct traffic information which should be exploited separately but existing multi-layer GNNs are incompetent to discriminate between their impact. Again, to capture the temporal interrelationship, recurrent neural networks are common in state-of-the-art approaches that often fail to capture long-range dependencies. Furthermore, traffic data shows repeated patterns in a daily or weekly period which should be addressed explicitly.  To address these limitations, we have designed a **S**implified **S**patio-temporal **T**raffic forecasting **GNN (SST-GNN)** that effectively encodes the spatial dependency by separately aggregating different neighborhood representations rather than with multiple layers and capture the temporal dependency with a simple yet effective weighted spatio-temporal aggregation mechanism. We capture the periodic traffic patterns by using a novel position encoding scheme with historical and current data in two different models. With extensive experimental analysis, we have shown that our model has significantly outperformed the state-of-the-art models on three real-world traffic datasets from the Performance Measurement System (PeMS).

# Model Architecture 

![Model Overview](model_architecture.png?raw=true "Title")

Inter-timestamp edges are introduced between identical nodes of consecutive timestamps e.g. an edge between a blue node at timestamp 09:05 AM and a blue node at timestamp 09:10 AM where the same color indicates identical nodes. Although both historical and current-day model deals with the same spatio-temporal graph consisting of all timestamp graphs over 5 min interval in the past hour of the prediction window, the historical model considers traffic features from last week to capture the repeated daily patterns while the current-day model uses only current day (e.g. Tuesday) information to find current day patterns in traffic data. Spatial dependency is captured through aggregating features from different neighborhoods on each timestamp graph while temporal dependency is preserved by performing temporal aggregation among the node representations learned from previous timestamps which are depicted in the Figure above. Finally, concatenation followed by weighted transformation is performed to compute the spatio-temporal embeddings of nodes which are used for traffic prediction.

# Weighted Spatio-Temporal Aggregation

![Weighted Spatio-Temporal Aggregation](st_aggregation.png?raw=true "Title")

Spatio-Temporal Aggregation Scheme: To capture complex spatio-temporal dependencies in traffic networks, the historical model concatenates the spatial embeddings from different hop neighborhoods at timestamp **t** with temporal embedding **Z̃<sub>H</sub><sup> < t > </sup>** - the weighted aggregation of **(Z<sub>H</sub><sup>< 1 ></sup>,...,Z<sub>H</sub><sup> < t-1 > </sup>)**, to learn spatio-temporal embeddings **Z<sub>H</sub><sup>< t ></sup>**. Similarly, current-day model performs the same process.

# Comarison with Baselines

![Comparison with Baselines](baseline_comparison.png?raw=true "Title")


# Envirnoment Set-Up 

Clone the git project:

```
$ git clone https://github.com/AmitRoy7781/SST-GNN
```

Create a new conda Environment and install required packages (Commands are for ubuntu 16.04)

```
$ conda create -n TrafficEnv python=3.7
$ conda activate TrafficEnv
$ pip install -r requirements.txt
```

# Basic Usage:

**Main Parameters:**

```
--dataset           The input traffic dataset(default:PeMSD7)
--GNN_layers        Number of layers in GNN(default:3)
--num_timestamps    Number of timestamps in Historical and current model(default:12)
--pred_len          Traffic Prediction after how many timestamps(default:3)
--epochs            Number of epochs during training(default:200)
--seed              Random seed. (default: 42)
--cuda              Use GPU if declared
--save_model        Save model if declared
--trained_model     Run pretrained model if declaired
```


**Train Model Using:**
```
$ python3 sst_gnn.py --cuda --dataset PeMSD7 --pred_len 3 --save_model
```

**Run Trained Model:**

Please download the trained SSTGNN models from [Google drive](https://drive.google.com/drive/folders/1xG28Cq3GSG_izfqf37y-__I4CCsc0ONJ?usp=sharing) and place it in `saved_model/PeMSD7` folder

```
$ python3 sst_gnn.py --cuda --dataset PeMSD7  --pred_len 3 --trained_model
```
