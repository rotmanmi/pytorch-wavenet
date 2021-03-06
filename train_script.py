import time
from wavenet_model import *
from audio_data import WavenetDataset
from wavenet_training import *
from model_logging import *
from scipy.io import wavfile
from argparse import ArgumentParser
import os

parser = ArgumentParser()

parser.add_argument('--cs', action='store_true')
parser.add_argument('--gain_factor', type=float, default=1.0)

args = parser.parse_args()

dtype = torch.FloatTensor
ltype = torch.LongTensor

use_cuda = torch.cuda.is_available()
if use_cuda:
    print('use gpu')
    dtype = torch.cuda.FloatTensor
    ltype = torch.cuda.LongTensor

model = WaveNetModel(layers=10,
                     blocks=3,
                     dilation_channels=32,
                     residual_channels=32,
                     skip_channels=1024,
                     end_channels=512,
                     output_length=16,
                     dtype=dtype,
                     bias=True,
                     args=args)

# model = load_latest_model_from('snapshots', use_cuda=True)
# model = torch.load('snapshots/some_model')

if use_cuda:
    print("move model to gpu")
    model.cuda()

print('model: ', model)
print('receptive field: ', model.receptive_field)
print('parameter count: ', model.parameter_count())

data = WavenetDataset(dataset_file='train_samples/bach_chaconne/dataset.npz',
                      item_length=model.receptive_field + model.output_length - 1,
                      target_length=model.output_length,
                      file_location='train_samples/bach_chaconne',
                      test_stride=500)
print('the dataset has ' + str(len(data)) + ' items')


def generate_and_log_samples(step):
    sample_length = 32000
    gen_model = load_latest_model_from('snapshots', use_cuda=False)
    print("start generating...")
    samples = generate_audio(gen_model,
                             length=sample_length,
                             temperatures=[0.5])
    tf_samples = tf.convert_to_tensor(samples, dtype=tf.float32)
    logger.audio_summary('temperature_0.5', tf_samples, step, sr=16000)

    samples = generate_audio(gen_model,
                             length=sample_length,
                             temperatures=[1.])
    tf_samples = tf.convert_to_tensor(samples, dtype=tf.float32)
    logger.audio_summary('temperature_1.0', tf_samples, step, sr=16000)
    print("audio clips generated")


cs = ''
gain = ''
if args.cs:
    cs = 'cs'
    gain = args.gain_factor

if not os.path.exists('snapshots{}{}'.format(cs, gain)):
    os.mkdir('snapshots{}{}'.format(cs, gain))

logger = TensorboardLogger(log_interval=200,
                           validation_interval=400,
                           generate_interval=800,
                           generate_function=generate_and_log_samples,
                           log_dir="logs/chaconne_model{}{}".format(cs, gain))

trainer = WavenetTrainer(model=model,
                         dataset=data,
                         lr=0.0001,
                         weight_decay=0.0,
                         snapshot_path='snapshots{}{}'.format(cs, gain),
                         snapshot_name='chaconne_model{}{}'.format(cs, gain),
                         snapshot_interval=1000,
                         logger=logger,
                         dtype=dtype,
                         ltype=ltype)

print('start training...')
trainer.train(batch_size=16,
              epochs=10,
              continue_training_at_step=0)
