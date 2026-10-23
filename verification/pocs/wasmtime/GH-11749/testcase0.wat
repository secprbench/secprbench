(module
  (type $a (array (mut i64)))
  (elem declare externref)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func $f2
    (local (ref null any))
    data.drop 0
    call $f2

    local.get 0
    ref.test nullref
    unreachable
  )
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func (export "") unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func unreachable)
  (func (export "entry") (result externref)
    call $f1

    i32.const 0
    array.new_default $a
    i32.const 0
    array.new_default $a
    elem.drop 0
    unreachable
  )
  (func $f1 call $f2 call $f2)
  (data)
)
