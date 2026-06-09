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
#include <mapf/mapf.hpp>

#ifndef MAPF__MAPF_SERVICE_HPP
#define MAPF__MAPF_SERVICE_HPP

class MAPFService : public RestServer
{
public:
  MAPFService(
    const std::string & server_url,
    int argc, char * argv[])
  :   RestServer(server_url,
      [this](http_request message)->void {handle_get(message);},
      [this](http_request message)->void {handle_post(message);},
      [this](http_request message)->void {handle_put(message);},
      [this](http_request message)->void {handle_del(message);}),
    mapf_(std::make_shared<MultiAgentPathFinding>(argc, argv))
  {
    // start();
  }

  void handle_get(http_request message)
  {

  }

  void handle_post(http_request message)
  {
    std::string msg_str = message.extract_string().get();
    // std::cout << "Request: " << msg_str << std::endl;
    std::string result = mapf_->test_function(msg_str);

    std::cout << "\n\n ========================= Result =============================== " <<
      std::endl;
    std::cout << result << std::endl;
    std::cout << " ================================================================ \n\n" <<
      std::endl;

    if (!result.empty()) {
      message.reply(status_codes::OK, result);
    } else {
      message.reply(status_codes::BadRequest, "GET request failed.");
    }
  }

  void handle_put(http_request message)
  {

  }

  void handle_del(http_request message)
  {

  }

  std::string service_callback(const std::string & service_request)
  {
  }

  ~MAPFService() {}

private:
  std::shared_ptr<MultiAgentPathFinding> mapf_;
};

#endif // MAPF__MAPF_SERVICE_HPP
