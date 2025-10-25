import torch.nn as nn
import torch
from sklearn.preprocessing import StandardScaler
import pickle
import pandas as pd

class HeartModel(nn.Module):
    def __init__(self):
        super(HeartModel, self).__init__()
        self.seq = nn.Sequential(
            nn.Linear(16, 64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, 512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )
    def forward(self, x):
        x = self.seq(x)
        return x

class Model():
    def __init__(self):
        self.__model = self.__load_model()
        self.__scaler = self.__load_scaler()
    def __load_model(self):
        model = torch.load("./models/model.pth")
        model.eval()
        return model
    def __load_scaler(self):
        __f = open("./scalers/scaler.pkl", "rb")
        __scaler = pickle.loads(__f.read())
        __f.close()
        return __scaler
    def __checkCondition(self, features, name, value):
        if value == 'Yes': features[name] = [1]
        else: features[name] = [0]
        return features
    def makePredictions(self, age, height, weight, ap_hi, ap_lo, smoke, active, alco, cholesterol, glucose, gender):
        input_features = {
            'age' : [int(age)*365],
            'height' : [int(height)],
            'weight' : [int(weight)],
            'ap_hi' : [int(ap_hi)],
            'ap_lo' : [int(ap_lo)],
            'smoke' : [0],
            'active' : [0],
            'alco' : [0],
            'cholesterol_1' : [0],
            'cholesterol_2' : [0],
            'cholesterol_3' : [0],
            'gluc_1' : [0],
            'gluc_2' : [0],
            'gluc_3' : [0],
            'gender_1' : [0],
            'gender_2' : [0],
        }

        input_features = self.__checkCondition(input_features, 'smoke', smoke)
        input_features = self.__checkCondition(input_features, 'active', active)
        input_features = self.__checkCondition(input_features, 'alco', alco)

        if gender == "Male": input_features["gender_2"] = [1]
        else: input_features["gender_1"] = [1]

        if cholesterol == "Normal": input_features["cholesterol_1"] = [1]
        elif cholesterol == "Above normal": input_features["cholesterol_2"] = [1]
        else: input_features["cholesterol_3"] = [1]

        if glucose == "Normal": input_features["gluc_1"] = [1]
        elif glucose == "Above normal": input_features["gluc_2"] = [1]
        else: input_features["gluc_3"] = [1]

        input_features = pd.DataFrame(input_features)

        x_scaled = self.__scaler.transform(input_features)

        input_tensor = torch.tensor(x_scaled, dtype=torch.float32)

        with torch.no_grad():
            output = self.__model(input_tensor)
            predictions = torch.sigmoid(output)
            predictions = (predictions > 0.5).float().numpy()
        
        return predictions[0]

