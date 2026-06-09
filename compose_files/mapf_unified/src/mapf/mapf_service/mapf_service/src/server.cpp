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


#include <mapf/server.hpp>

// /// Define an internal callback to handle incoming messages
// void Server::on_message(websocketpp::connection_hdl hdl, HTTPServer::message_ptr msg)
// {
//     const auto msg_string = msg->get_payload();
//     if (!msg_string.empty())
//     {
//         std::string response = msg_callback(msg_string);
//         echo_server.send(hdl, response, websocketpp::frame::opcode::text);
//     }
// }

// /// Start HTTPServer
// void Server::start()
// {
//     std::cout << "Start Server" << std::endl;
//     // Start the ASIO io_service run loop
//     server_thread_ = std::thread(
//         [this](){echo_server.run();});
// }

// /// Stop HTTPServer
// void Server::stop()
// {
//     std::cout << "Stop Server" << std::endl;
//     if (server_thread_.joinable())
//     {
//         echo_server.stop_listening();
//         echo_server.stop();
//         // TODO: properly close all connections
//         server_thread_.join();
//     }
// }

// //==============================================================================
// Server::Server(
//     const int port,
//     ApiMessageCallback callback) : msg_callback(callback)
// {
//     std::cout << "Run websocket server with port " << port << std::endl;
//     try
//     {
//       // Hide all logs from websocketpp
//       echo_server.clear_access_channels(websocketpp::log::alevel::all);
//       // enable reuse of address if server is respawned
//       echo_server.set_reuse_addr(true);
//       echo_server.init_asio();

//       // Register our message handler
//       using websocketpp::lib::placeholders::_1;
//       using websocketpp::lib::placeholders::_2;
//       echo_server.set_message_handler(
//         [=](const auto& hdl, const auto& msg)
//         {
//             on_message(hdl, msg);
//         });

//       echo_server.listen(port);
//       echo_server.start_accept();
//     }
//     catch (const websocketpp::exception& e)
//     {
//       std::cout << e.what() << std::endl;
//     }
//     catch (...)
//     {
//       std::cout << "other exception" << std::endl;
//     }
// }

// Server::~Server(){
//     stop();
// }
