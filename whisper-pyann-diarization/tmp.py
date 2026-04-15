import numpy as np
row1 = {'SPEAKER_00': 21.667442, 'SPEAKER_00_fuzz': 100}
row2 = {'SPEAKER_01': 7.7048755, 'SPEAKER_01_fuzz': 741}

a = np.array([[row1['SPEAKER_00'], row1['SPEAKER_00_fuzz']],
          [row2['SPEAKER_01'], row2['SPEAKER_01_fuzz']]
          ]
         )
print((a.max(axis=0) - 0))
a = a/ (a.max(axis=0) - 0)
print("al", a)
if np.sum(a[0] - a[1]) > 0:
    print('SPEAKER_00 has greater value')
else:
    print('SPEAKER_01 has greater value')

# np.
# print(np)