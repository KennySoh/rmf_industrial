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


#ifndef MAPF__SERVER_HPP
#define MAPF__SERVER_HPP

// #include <optional>
// #include <websocketpp/config/asio_no_tls.hpp>
// #include <websocketpp/server.hpp>

// #include <iostream>
// #include <exception>
// #include <functional>
// #include <thread>

// using HTTPServer = websocketpp::server<websocketpp::config::asio>;

// class Server
// {
// public:
//   using ApiMessageCallback = std::function<std::string(const std::string&)>;
//   Server(const int port,
//     ApiMessageCallback callback);


//   void on_message(websocketpp::connection_hdl, HTTPServer::message_ptr msg);

//   /// Start Server
//   void start();

//   /// Stop Server
//   void stop();

//   ~Server();

// private:
//     HTTPServer echo_server;
//     ApiMessageCallback msg_callback;
//     std::thread server_thread_;
// };

#include <cpprest/http_client.h>
#include <cpprest/http_listener.h>
#include <cpprest/filestream.h>
#include <cpprest/uri.h>
#include <cpprest/json.h>
#include <nlohmann/json.hpp>

#include <chrono>
#include <iostream>
#include <thread>
#include <future>

using namespace utility; // Common utilities like string conversions
using namespace web; // Common features like URIs.
using namespace web::http; // Common HTTP functionality
using namespace web::http::client;
using namespace web::http::experimental; // HTTP listener
using namespace concurrency::streams; // Asynchronous streams
using namespace std;


class RestServer
{
public:
  RestServer(
    const std::string & server_url,
    std::function<void(http_request)> get_handler,
    std::function<void(http_request)> post_handler,
    std::function<void(http_request)> put_handler,
    std::function<void(http_request)> del_handler)
  : listener_(
      std::make_unique<listener::http_listener>(U(server_url))),
    server_url_(server_url)
  {
    listener_->support(methods::GET, get_handler);
    listener_->support(methods::POST, post_handler);
    listener_->support(methods::PUT, put_handler);
    listener_->support(methods::DEL, del_handler);
    server_run_future = std::async(
      std::launch::async,
      [this]()->void
      {
        start_server();
      });
  }

  ~RestServer() {}

  bool start_server()
  {
    try {
      listener_->open()
      .then([]() {printf("\nStarting REST Server\n");})
      .wait();
      while (true) {}
      return true;
    } catch (const std::exception & e) {
      printf("Error exception:%s\n", e.what());
    }
    return false;
  }

  std::future<void> server_run_future;

  std::unique_ptr<listener::http_listener> listener_;

  std::string server_url_;
};

#endif // MAPF__SERVER_HPP
