(component
  (import "wasi:http/types@0.2.0" (instance $types
    (export "incoming-request" (type (sub resource)))
    (export "response-outparam" (type (sub resource)))
  ))
  (alias export $types "incoming-request" (type $incoming-request))
  (alias export $types "response-outparam" (type $response-outparam))

  (core module $m
    (func (export "handle") (param i32 i32))
  )
  (core instance $i (instantiate $m))

  (func $handle (param "request" (own $incoming-request)) (param "response-out" (own $response-outparam))
    (canon lift (core func $i "handle"))
  )

  (instance $inst
    (export "handle" (func $handle))
  )
  (export "wasi:http/incoming-handler@0.2.0" (instance $inst))
)
