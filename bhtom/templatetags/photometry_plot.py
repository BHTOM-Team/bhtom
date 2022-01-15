import json
from collections import namedtuple
from typing import Optional, Tuple

import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
from dash.dependencies import State
from dash_extensions.enrich import Output, Input
from django_plotly_dash import DjangoDash
from tom_dataproducts.models import ReducedDatum
from datetime import datetime, timedelta
from django.utils import timezone

from bhtom.models import refresh_reduced_data_view
from bhtom.templatetags.photometry_tags import photometry_plot_data

PlotPointData = namedtuple('PlotPointData', ['reduced_datum', 'trace_index', 'point_index'])

app = DjangoDash(name='PhotometryPlot',
                 external_stylesheets=[dbc.themes.BOOTSTRAP])

previous_target_name = -1
selected_point: Optional[PlotPointData] = None

previous_yes_n_clicks = 0
previous_no_n_clicks = 0

fig = go.Figure(data=[], layout=go.Layout(
        yaxis=dict(autorange='reversed'),
        xaxis=dict(title='UTC time'),
        height=600,
        width=750
    ))


app.layout = html.Div([
    dbc.Modal(
        [
            dbc.ModalBody("Do you want to delete this point?"),
            dbc.ModalFooter(
                [dbc.Button(
                    "Yes",
                    id='yes-delete-point',
                    className='ms-auto',
                    n_clicks=0
                ),
                dbc.Button(
                    "No",
                    id='no-delete-point',
                    className='ms-auto',
                    n_clicks=0
                ),],
            )
        ],
        id='delete-point-modal',
        centered=True,
        is_open=False
    ),
    dcc.Input(id='target_id', persistence=False, value='', type='hidden'),
    dcc.Input(id='user_id', persistence=False, value='', type='hidden'),
    dcc.Graph(
        id='photometry-plot',
        figure=fig
    ),
], style={'height': '800px'})


@app.callback(
    [Output("delete-point-modal", "is_open"), Output("photometry-plot", "figure")],
    [Input("photometry-plot", "clickData"), Input('target_id', 'value'), Input('user_id', 'value'),
     Input("yes-delete-point", "n_clicks"), Input("no-delete-point", "n_clicks")],
    [State("delete-point-modal", "is_open")],
)
def toggle_modal(clickData, target_id, user_id, yes_n_clicks, no_n_clicks, is_open):
    global selected_point, previous_target_name, previous_yes_n_clicks, previous_no_n_clicks

    if target_id != previous_target_name:
        previous_target_name = target_id
        selected_point = None
        plot_data = photometry_plot_data(target_id=target_id, user_id=user_id)
        fig.data = []
        fig.add_traces(plot_data)
        fig.update_layout(transition_duration=500)

    if yes_n_clicks != previous_yes_n_clicks:
        previous_yes_n_clicks = yes_n_clicks

        if selected_point and try_to_delete_point(selected_point):
            new_x = list(fig.data[selected_point.trace_index]['x'])
            new_x.pop(selected_point.point_index)

            new_y = list(fig.data[selected_point.trace_index]['y'])
            new_y.pop(selected_point.point_index)

            fig.data[selected_point.trace_index]['x'] = tuple(new_x)
            fig.data[selected_point.trace_index]['y'] = tuple(new_y)
            fig.update_layout(transition_duration=500)

        selected_point = None

        return not is_open, fig

    if no_n_clicks != previous_no_n_clicks:
        previous_no_n_clicks = no_n_clicks
        return not is_open, fig

    if clickData:
        points_info_list = clickData.get('points', [])
        if len(points_info_list) > 0:
            points_info = points_info_list[0]
            trace_index = points_info.get('curveNumber')
            point_index = points_info.get('pointIndex')
            timestamp = points_info.get('x')
            mag = points_info.get('y')
            filter = fig.data[trace_index].name

            maybe_reduced_point: Optional[ReducedDatum] = try_to_fetch_point(target_id=target_id,
                                                                             point_timestamp=timestamp,
                                                                             point_mag=mag,
                                                                             point_band=filter)
            if maybe_reduced_point:
                selected_point = PlotPointData(reduced_datum=maybe_reduced_point,
                                               trace_index=trace_index,
                                               point_index=point_index)
                return not is_open, fig

        return is_open, fig

    return is_open, fig


def try_to_fetch_point(target_id, point_timestamp, point_mag, point_band) -> Optional[ReducedDatum]:
    from django.utils.timezone import make_aware

    def load_datum_json(json_values):
        if json_values:
            if type(json_values) is dict:
                return json_values
            else:
                return json.loads(json_values.replace("\'", '"'))
        else:
            return {}

    timestamp = make_aware(datetime.strptime(point_timestamp, '%Y-%m-%d %H:%M:%S.%f'), timezone=timezone.utc)

    points_with_timestamp = ReducedDatum.objects.filter(target_id=target_id, source_name='CPCS',
                                                        timestamp__gte=timestamp-timedelta(milliseconds=10),
                                                        timestamp__lte=timestamp+timedelta(milliseconds=10))
    for point in points_with_timestamp:
        try:
            value = load_datum_json(point.value)
            if value["magnitude"]==point_mag and value["filter"]==point_band:
                return point
        except Exception:
            return None


def try_to_delete_point(plot_point_data: PlotPointData) -> bool:
    try:
        cpcs_id: int = int(plot_point_data.reduced_datum.source_location.split('&')[-1])
        print(f'Trying to delete a point with cpcs_id {cpcs_id}')
        plot_point_data.reduced_datum.delete()
        refresh_reduced_data_view()
        return True
    except Exception as e:
        return False
