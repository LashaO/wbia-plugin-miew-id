### TODO """preprocessing scripts - filtering, subsampling, splitting"""
import json
import os
import pandas as pd
from sklearn.preprocessing import LabelEncoder



def load_json(file_path):
    with open(file_path) as f:
        data = json.load(f)
    return data

def load_to_df(anno_path):
    data = load_json(anno_path)

    dfa = pd.DataFrame(data['annotations'])
    dfi = pd.DataFrame(data['images'])

    dfi = dfi.drop_duplicates(subset=['uuid'])

    merge_on_uuid = 'image_uuid' in dfa.columns and 'uuid' in dfi.columns
    if merge_on_uuid:
        print('Merging on image uuid')
        df = dfa.merge(dfi, left_on='image_uuid', right_on='uuid')
    else:
        df = dfa.merge(dfi, left_on='image_id', right_on='id') 


    return df

def filter_viewpoint_df(df, viewpoint_list):
    df = df[df['viewpoint'].isin(viewpoint_list)]
    return df

def filter_min_names_df(df, n_filter_min, filter_key='name_species'):
    print(f"Filtering by min {n_filter_min} annotations per {filter_key}")
    df = df.groupby(filter_key).filter(lambda g: len(g)>=n_filter_min)
    return df

def subsample_max_df(df, n_subsample_max, subsample_name_key='name_species'):
    print(f"Subsampling by max {n_subsample_max} annotations per {subsample_name_key}")
    df = df.groupby(subsample_name_key).apply(lambda g: g.sample(frac=1, random_state=0).head(n_subsample_max)).sample(frac=1, random_state=1).reset_index(drop=True)
    return df

def convert_name_to_id(names):
    le = LabelEncoder()
    names_id = le.fit_transform(names)
    return names_id

def preprocess_data(anno_path, name_keys=['name'], convert_names_to_ids=True, viewpoint_list=None, n_filter_min=None, n_subsample_max=None):

    df = load_to_df(anno_path)

    print(f'** Loaded {anno_path} **')
    print('     ', f'Found {len(df)} annotations')

    df['name'] = df[name_keys].apply(lambda row: '_'.join(row.values.astype(str)), axis=1)

    # df.loc[df['name_species'].isna(), 'name_species'] = df.loc[df['name_species'].isna(), 'name'].astype(str) + '_' + df.loc[df['name_species'].isna(), 'species']
    df['name_species'] = df['name'] + '_' + df['species']

    df['name_orig'] = df['name'].copy()

    if viewpoint_list:
        df = filter_viewpoint_df(df, viewpoint_list)
        print('     ', len(df), 'annotations remain after filtering by viewpoint list', viewpoint_list)
    
    if n_filter_min:
        df = filter_min_names_df(df, n_filter_min)
        print('     ', len(df), 'annotations remain after filtering by min', n_filter_min)

    if n_subsample_max:
        df = subsample_max_df(df, n_subsample_max)
        print('     ', len(df), 'annotations remain after subsampling by max', n_subsample_max)

    if convert_names_to_ids:
        names = df['name'].values
        names_id = convert_name_to_id(names)
        df['name'] = names_id
    return df

if __name__ == "__main__":
    pass