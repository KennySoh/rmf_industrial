// Copyright 2024 ROS Industrial Consortium Asia Pacific
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
#include <websocketpp/config/asio_no_tls_client.hpp>

#include <websocketpp/client.hpp>

#include <iostream>

typedef websocketpp::client<websocketpp::config::asio_client> client;

using websocketpp::lib::placeholders::_1;
using websocketpp::lib::placeholders::_2;
using websocketpp::lib::bind;

// pull out the type of messages sent by our config
typedef websocketpp::config::asio_client::message_type::ptr message_ptr;

// Handlers
void on_open(client * c, websocketpp::connection_hdl hdl)
{
  std::string msg =
    "{\n  \"mapfile\":\"building.yaml\",\n  \"solver\" : \"ECBS\",\n  \"max_computation_time\" : 5000,\n  \"max_timestep\" : 1000,\n  \"tasks\": [\n    {\n      \"agent_name\" : \"agent_1\",\n        \"start_position\" :\n      {\n        \"x\" : 30,\n        \"y\" : 60\n      },\n      \"end_position\" :\n      {\n        \"x\" : 300,\n        \"y\" : 90\n      }\n    },\n    {\n      \"agent_name\" : \"agent_2\",\n      \"start_position\" :\n      {\n        \"x\" : 30,\n        \"y\" : 30\n      },\n      \"end_position\" :\n      {\n        \"x\" : 300,\n        \"y\" : 60\n      }\n    }\n  ]\n}";
  c->send(hdl, msg, websocketpp::frame::opcode::text);
  c->get_alog().write(websocketpp::log::alevel::app, "Sent Message: " + msg);
}

void on_fail(client * c, websocketpp::connection_hdl hdl)
{
  c->get_alog().write(websocketpp::log::alevel::app, "Connection Failed");
}

void on_message(client * c, websocketpp::connection_hdl hdl, message_ptr msg)
{
  c->get_alog().write(websocketpp::log::alevel::app, "Received Reply: " + msg->get_payload());
  c->close(hdl, websocketpp::close::status::normal, "");
}

void on_close(client * c, websocketpp::connection_hdl hdl)
{
  c->get_alog().write(websocketpp::log::alevel::app, "Connection Closed");
}

int main(int argc, char * argv[])
{
  client c;

  std::string uri = "ws://localhost:8888";

  if (argc == 2) {
    uri = argv[1];
  }

  try {
    // set logging policy if needed
    c.clear_access_channels(websocketpp::log::alevel::frame_header);
    c.clear_access_channels(websocketpp::log::alevel::frame_payload);
    //c.set_error_channels(websocketpp::log::elevel::none);

    // Initialize ASIO
    c.init_asio();

    // Register our handlers
    c.set_open_handler(bind(&on_open, &c, ::_1));
    c.set_fail_handler(bind(&on_fail, &c, ::_1));
    c.set_message_handler(bind(&on_message, &c, ::_1, ::_2));
    c.set_close_handler(bind(&on_close, &c, ::_1));

    // Create a connection to the given URI and queue it for connection once
    // the event loop starts
    websocketpp::lib::error_code ec;
    client::connection_ptr con = c.get_connection(uri, ec);
    c.connect(con);

    // Start the ASIO io_service run loop
    c.run();
  } catch (const std::exception & e) {
    std::cout << e.what() << std::endl;
  } catch (websocketpp::lib::error_code e) {
    std::cout << e.message() << std::endl;
  } catch (...) {
    std::cout << "other exception" << std::endl;
  }
}
