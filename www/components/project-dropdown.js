import React from 'react';
import ReactDOM from 'react-dom';

function ProjectDropdown(props)  {
    return (<h1>Hello {props.title}</h1>)
}

ReactDOM.render(
  <ProjectDropdown title="World" />,
  document.getElementById('root')
);

export default ProjectDropdown;