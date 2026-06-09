#include <cmath>

template<typename T>
[[nodiscard]] static T Round(T number)
{
  return (number >
         0) ? ::floor(number + static_cast<T>(0.5)) : ::ceil(number - static_cast<T>(0.5));
}

template<typename T>
[[nodiscard]] static T Round(T number, int places)
{
  const T shift = pow(static_cast<T>(10.0), places);
  return Round(number * shift) / shift;
}
